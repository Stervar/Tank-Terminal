import curses
import time
import random
import sys
from curses import textpad
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from enum import Enum
from queue import PriorityQueue

# Определение конфигураций уровней
LEVEL_CONFIGS = {
    1: {
        "blocks": [(1, 1, "brick"), (2, 2, "metal")],
        "flag_position": (5, 5),
        "spawn_points": [(0, 0), (0, 1)],
        "player_start": (3, 3)
    },
    2: {
        "blocks": [(1, 1, "brick"), (2, 2, "bush")],
        "flag_position": (5, 5),
        "spawn_points": [(0, 0), (0, 1)],
        "player_start": (3, 3)
    },
    # Добавьте дополнительные уровни по мере необходимости
}

# Константы игры
GAME_TITLE = "Tank Battle"
FPS = 60
FRAME_TIME = 1.0 / FPS

# Перечисления для игровых состояний
class GameState(Enum):
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    VICTORY = "victory"

class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right "

# Базовый класс для всех игровых объектов
class GameObject(ABC):
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.symbol = ""
        self.color_pair = 1

    @abstractmethod
    def update(self, game_map: 'GameMap') -> None:
        pass

    @abstractmethod
    def render(self, screen) -> None:
        pass

    def get_position(self) -> Tuple[int, int]:
        return (self.x, self.y)

# Класс для представления блоков на карте
@dataclass
class Block(GameObject):
    METAL = "█"
    BRICK = "▒"
    BUSH = "♣"
    AIR = " "

    def __init__(self, x: int, y: int, block_type: str, durability: int = 4):
        super().__init__(x, y)
        self.block_type = block_type
        self.durability = durability
        self.symbol = self._get_symbol()
        self.color_pair = self._get_color_pair()

    def _get_symbol(self) -> str:
        return {
            "metal": Block.METAL,
            "brick": Block.BRICK,
            "bush": Block.BUSH,
            "air": Block.AIR
        }[self.block_type]

    def _get_color_pair(self) -> int:
        return {
            "metal": 1,
            "brick": 2,
            "bush": 3,
            "air": 0
        }[self.block_type]

    def update(self, game_map: 'GameMap') -> None:
        if self.durability <= 0 and self.block_type == "brick":
            self.block_type = "air"
            self.symbol = Block.AIR
            self.color_pair = 0

    def render(self, screen) -> None:
        if self.block_type != "air":
            try:
                screen.addch(self.y, self.x, self.symbol, 
                           curses.color_pair(self.color_pair))
            except curses.error:
                pass

# Класс для снарядов
class Projectile(GameObject):
    def __init__(self, x: int, y: int, direction: Direction, damage: int, 
                 owner: 'Tank'):
        super().__init__(x, y)
        self.direction = direction
        self.damage = damage
        self.owner = owner
        self.symbol = "•"
        self.color_pair = 4
        self.speed = 2

    def update(self, game_map: 'GameMap') -> None:
        if self.direction == Direction.UP:
            self.y -= self.speed
        elif self.direction == Direction.DOWN:
            self.y += self.speed
        elif self.direction == Direction.LEFT:
            self.x -= self.speed
        elif self.direction == Direction.RIGHT:
            self.x += self.speed

        # Проверка столкновений
        block = game_map.get_block(self.x, self.y)
        if block and block.block_type != "air":
            if block.block_type == "brick":
                block.durability -= self.damage
            return True
        return False

    def render(self, screen) -> None:
        try:
            screen.addch(self.y, self.x, self.symbol, 
                        curses.color_pair(self.color_pair))
        except curses.error:
            pass

# Базовый класс для всех типов танков
class Tank(GameObject):
    def __init__(self, x: int, y: int, tank_type: str):
        super().__init__(x, y)
        self.tank_type = tank_type
        self.direction = Direction.UP
        self.health = self._get_initial_health()
        self.speed = self._get_speed()
        self.reload_time = self._get_reload_time()
        self.last_shot_time = 0
        self.symbol = "▲"
        self.color_pair = self._get_color_pair()
        self.projectiles: List[Projectile] = []

    def _get_initial_health(self) -> int:
        return {
            "light": 1,
            "medium": 2,
            "heavy": 3,
            "boss": 20
        }[self.tank_type]

    def _get_speed(self) -> float:
        return {
            "light": 1.5,
            "medium": 1.0,
            "heavy": 0.5,
            "boss": 0.3
        }[self.tank_type]

    def _get_reload_time(self) -> float:
        return {
            "light": 0.5,
            "medium": 1.0,
            "heavy": 1.5,
            "boss": 2.0
        }[self.tank_type]

    def _get_color_pair(self ) -> int:
        return {
            "light": 5,
            "medium": 6,
            "heavy": 7,
            "boss": 8
        }[self.tank_type]

    def shoot(self, current_time: float) -> Optional[Projectile]:
        if current_time - self.last_shot_time >= self.reload_time:
            self.last_shot_time = current_time
            
            # Определяем начальную позицию снаряда
            projectile_x = self.x
            projectile_y = self.y
            
            if self.direction == Direction.UP:
                projectile_y -= 1
            elif self.direction == Direction.DOWN:
                projectile_y += 1
            elif self.direction == Direction.LEFT:
                projectile_x -= 1
            elif self.direction == Direction.RIGHT:
                projectile_x += 1
                
            return Projectile(projectile_x, projectile_y, self.direction, 
                            self._get_damage(), self)
        return None

    def _get_damage(self) -> int:
        return {
            "light": 1,
            "medium": 2,
            "heavy": 3,
            "boss": 5
        }[self.tank_type]

    def update(self, game_map: 'GameMap') -> None:
        # Обновление состояния танка
        pass

    def render(self, screen) -> None:
        try:
            # Отрисовка танка с учетом направления
            symbol = {
                Direction.UP: "▲",
                Direction.DOWN: "▼",
                Direction.LEFT: "◄",
                Direction.RIGHT: "►"
            }[self.direction]
            
            screen.addch(self.y, self.x, symbol, 
                        curses.color_pair(self.color_pair))
            
            # Отрисовка здоровья для босса
            if self.tank_type == "boss":
                health_bar = f"HP: {'█' * self.health}"
                screen.addstr(self.y - 1, self.x - len(health_bar) // 2, 
                            health_bar, curses.color_pair(self.color_pair))
        except curses.error:
            pass

# Класс игрока
class PlayerTank(Tank):
    def __init__(self, x: int, y: int):
        super().__init__(x, y, "medium")
        self.lives = 3
        self.score = 0
        self.current_weapon = "standard"
        self.weapons = {
            "standard": {"damage": 1, "reload": 0.5},
            "medium": {"damage": 2, "reload": 1.0},
            "heavy": {"damage": 3, "reload": 1.5}
        }

    def switch_weapon(self) -> None:
        weapons = list(self.weapons.keys())
        current_index = weapons.index(self.current_weapon)
        self.current_weapon = weapons[(current_index + 1) % len(weapons)]
        self.reload_time = self.weapons[self.current_weapon]["reload"]

    def update(self, game_map: 'GameMap') -> None:
        # Проверка столкновений и обновление состояния
        new_x = self.x
        new_y = self.y
        
        keys = game_map.get_pressed_keys()
        
        if keys.get(curses.KEY_UP):
            self.direction = Direction.UP
            new_y -= self.speed
        elif keys.get(curses.KEY_DOWN):
            self.direction = Direction.DOWN
            new_y += self.speed
        elif keys.get(curses.KEY_LEFT):
            self.direction = Direction.LEFT
            new_x -= self.speed
        elif keys.get(curses.KEY_RIGHT):
            self.direction = Direction.RIGHT
            new_x += self.speed

        # Проверка возможности движения
        if game_map.can_move_to(new_x, new_y):
            self.x = new_x
            self.y = new_y

# Класс противника
class EnemyTank(Tank):
    def __init__(self, x: int, y: int, tank_type: str):
        super().__init__(x, y, tank_type)
        self.target = None
        self.path = []
        self.last_path_update = 0
        self.path_update_interval = 1.0

    def update(self, game_map: 'GameMap') -> None:
        current_time = time.time()
        
        # Обновление пути к цели
        if current_time - self.last_path_update >= self.path_update_interval:
            self.last_path_update = current_time
            self.update_path(game_map)

        # Движение по пути
        if self.path:
            next_x, next_y = self.path[0]
            
            # Определение направления движения
            if next_x > self.x:
                self.direction = Direction.RIGHT
            elif next_x < self.x:
                self.direction = Direction.LEFT
            elif next_y > self.y:
                self.direction = Direction.DOWN
            elif next_y < self.y:
                self.direction = Direction.UP

            # Проверка возможности движения
            if game_map.can_move_to(next_x, next_y):
                self.x = next_x
                self.y = next_y
                self.path.pop(0)

    def update_path(self, game_map: 'GameMap') -> None:
        # Поиск пути к флагу или игроку
        if game_map.player:
            self.target = game_map.player.get_position()
        else:
            self.target = game_map.flag_position

        if self.target:
            self.path = self.find_path(game_map, self.target)

    def find_path(self, game_map: 'GameMap', target: Tuple[int, int]) -> List[Tuple[int, int]]:
        # Реализация алгоритма поиска пути (A*)
        return self._a_star(game_map, (self.x, self.y), target)

    def _a_star(self, game_map: 'GameMap', start: Tuple[int, int], 
                goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        # Реализация A* алгоритма
        frontier = PriorityQueue()
        frontier.put(start, 0)
        came_from = {start: None}
        cost_so_far = {start: 0}

        while not frontier.empty():
            current = frontier.get()

            if current == goal:
                break

            for next_pos in game_map.get_neighbors(current[0], current[1]):
                new_cost = cost_so_far[current] + 1

                if next_pos not in cost_so_far or new_cost < cost_so_far[next_pos]:
                    cost_so_far[next_pos] = new_cost
                    priority = new_cost + self._heuristic(next_pos, goal)
                    frontier.put(next_pos, priority)
                    came_from[next_pos] = current

        return self._reconstruct_path(came_from, start, goal)

    def _heuristic(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        # Манхэттенское расстояние
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def _reconstruct_path(self, came_from: Dict, start: Tuple[int, int], 
                         goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        current = goal
        path = []

        while current != start:
            path.append(current)
            current = came_from[current]

        path.append(start)
        path.reverse()
        return path

# Класс для управления картой и игровым миром
class GameMap:
    def __init__(self, width: int, height: int, level: int):
        self.width = width
        self.height = height
        self.level = level
        self.blocks: List[List[Block]] = []
        self.tanks: List[Tank] = []
        self.projectiles: List[Projectile] = []
        self.player: Optional[PlayerTank] = None
        self.flag_position: Tuple[int, int] = (0, 0)
        self.spawn_points: List[Tuple[int, int]] = []
        self.next_spawn_time = 0
        self.spawn_interval = 10  # секунды между появлением танков
        self.killed_tanks = 0
        self.deaths = 0
        self.start_time = time.time()
        self.pressed_keys = {}

    def initialize_level(self) -> None:
        """Инициализация уровня на основе его номера"""
        self.blocks = [[Block(x, y, "air") for x in range(self.width)] 
                      for y in range(self.height)]
        
        # Загрузка конфигурации уровня
        level_config = LEVEL_CONFIGS[self.level]
        
        # Установка блоков
        for block_data in level_config["blocks"]:
            x, y, block_type = block_data
            self.blocks[y][x] = Block(x, y, block_type)

        # Установка флага
        self.flag_position = level_config["flag_position"]
        
        # Установка точек появления
        self.spawn_points = level_config["spawn_points"]
        
        # Создание игрока
        player_pos = level_config["player_start"]
        self.player = PlayerTank(*player_pos)
        
        # Инициализация списка танков для уровня
        self.remaining_tanks = self._get_level_tanks()

    def _get_level_tanks(self) -> List[Dict]:
        """Получение списка танков для текущего уровня"""
        return {
            1: [{"type": "normal", "count": 3}],
            2: [{"type": "normal", "count": 5 }],
            3: [{"type": "normal", "count": 7}],
            4: [{"type": "normal", "count": 10}],
            5: [{"type": "normal", "count": 8}, 
                {"type": "light", "count": 2}],
            6: [{"type": "normal", "count": 8}, 
                {"type": "light", "count": 2},
                {"type": "medium", "count": 1}],
            7: [{"type": "normal", "count": 8}, 
                {"type": "light", "count": 2},
                {"type": "medium", "count": 2}],
            8: [{"type": "normal", "count": 8}, 
                {"type": "light", "count": 2},
                {"type": "medium", "count": 2},
                {"type": "heavy", "count": 1}],
            9: [{"type": "normal", "count": 8}, 
                {"type": "light", "count": 2},
                {"type": "medium", "count": 2},
                {"type": "heavy", "count": 2}],
            10: [{"type": "normal", "count": 10}, 
                {"type": "light", "count": 2},
                {"type": "medium", "count": 2},
                {"type": "heavy", "count": 2}],
            11: [{"type": "boss", "count": 1}]
        }[self.level]

    def update(self, current_time: float) -> None:
        """Обновление состояния игрового мира"""
        # Спавн новых танков
        if (self.remaining_tanks and 
            current_time >= self.next_spawn_time):
            self._spawn_tank()
            self.next_spawn_time = current_time + self.spawn_interval

        # Обновление танков
        for tank in self.tanks[:]:
            tank.update(self)
            
            # Проверка выстрелов
            projectile = tank.shoot(current_time)
            if projectile:
                self.projectiles.append(projectile)

        # Обновление снарядов
        for projectile in self.projectiles[:]:
            if projectile.update(self):
                self.projectiles.remove(projectile)

        # Проверка столкновений
        self._check_collisions()

        # Обновление блоков
        for row in self.blocks:
            for block in row:
                block.update(self)

    def _spawn_tank(self) -> None:
        """Создание нового танка"""
        if not self.remaining_tanks:
            return

        spawn_point = random.choice(self.spawn_points)
        tank_data = self.remaining_tanks[0]
        
        if tank_data["count"] > 0:
            new_tank = EnemyTank(*spawn_point, tank_data["type"])
            self.tanks.append(new_tank)
            tank_data["count"] -= 1
            
            if tank_data["count"] == 0:
                self.remaining_tanks.pop(0)

    def _check_collisions(self) -> None:
        """Проверка всех столкновений"""
        # Проверка столкновений снарядов с танками
        for projectile in self.projectiles[:]:
            for tank in self.tanks[:]:
                if (projectile.x == tank.x and 
                    projectile.y == tank.y and 
                    projectile.owner != tank):
                    tank.health -= projectile.damage
                    self.projectiles.remove(projectile)
                    
                    if tank.health <= 0:
                        self.tanks.remove(tank)
                        self.killed_tanks += 1
                        break

            # Проверка попадания в игрока
            if (self.player and 
                projectile.x == self.player.x and 
                projectile.y == self.player.y and 
                projectile.owner != self.player):
                self.player.lives -= 1
                self.deaths += 1
                self.projectiles.remove(projectile)
                
                if self.player.lives <= 0:
                    return GameState.GAME_OVER

            # Проверка попадания во флаг
            if (projectile.x == self.flag_position[0] and 
                projectile.y == self.flag_position[1]):
                return GameState.GAME_OVER

    def can_move_to(self, x: int, y: int) -> bool:
        """Проверка возможности движения в указанную позицию"""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
            
        block = self.blocks[y][x]
        return block.block_type in ["air", "bush"]

    def get_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Получение списка соседних клеток для pathfinding"""
        neighbors = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            new_x, new_y = x + dx, y + dy
            if self.can_move_to(new_x, new_y):
                neighbors.append((new_x, new_y))
        return neighbors

    def render(self, screen) -> None:
        """Отрисовка всего игрового мира"""
        # Отрисовка блоков
        for row in self.blocks:
            for block in row:
                block.render(screen)

        # Отрисовка танков
        for tank in self.tanks:
            tank.render(screen)

        # Отрисовка снарядов
        for projectile in self.projectiles:
            projectile.render(screen)

        # Отрисовка игрока
        if self.player:
            self.player.render(screen)

        # Отрисовка флага
        screen.addch(self.flag_position[1], self.flag_position[0], "F", 
                    curses.color_pair(1))

    def get_pressed_keys(self) -> Dict:
        return self.pressed_keys

class UserInterface:
    def __init__(self, screen):
        self.screen = screen
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(7, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(8, curses.COLOR_RED, curses.COLOR_BLACK)

    def show_main_menu(self) -> str:
        """Отображение главного меню"""
        menu_items = [
            "╔═══════════════════════════════╗",
            "║         TANK BATTLE           ║",
            "╠═══════════════════════════════╣",
            "║  1. Начать новую игру         ║",
            "║  2. Выбрать уровень           ║",
            "║  3. Показать инструкции       ║",
            "║  4. Выйти                     ║",
            "╚═══════════════════════════════╝"
        ]

        while True:
            self.screen.clear()
            h, w = self.screen.getmaxyx()
            
            for i, item in enumerate(menu_items):
                x = w//2 - len(item)//2
                y = h//2 - len(menu_items)//2 + i
                self.screen.addstr(y, x, item, curses.color_pair(1))

            self.screen.refresh()
            
            key = self.screen.getch()
            if key in [ord('1'), ord('2'), ord('3'), ord('4')]:
                return str(chr(key))

    def show_level_selection(self) -> int:
        """Меню выбора уровня"""
        levels = [
            "╔═══════════════════════════════╗",
            "║       ВЫБЕРИТЕ УРОВЕНЬ        ║",
            "╠═══════════════════════════════╣"
        ]
        
        for i in range(1, 12):
            if i == 11:
                levels.append(f"║  {i}. Босс                      ║")
            else:
                levels.append(f"║  {i}. Уровень {i}                 ║")
        
        levels.append("╚═══════════════════════════════╝")

        while True:
            self.screen.clear()
            h, w = self.screen.getmaxyx()
            
            for i, item in enumerate(levels):
                x = w//2 - len(item)//2
                y = h//2 - len(levels)//2 + i
                self.screen.addstr(y, x, item, curses.color_pair(1))

            self.screen.refresh()
            
            key = self.screen.getch()
            if ord('1') <= key <= ord('9') or key in [ord('0'), ord('b')]:
                return int(chr(key))

    def show_instructions(self) -> None:
        """Отображение инструкций"""
        instructions = [
            "╔═══════════════════════════════════════════╗",
            "║ ИНСТРУКЦИИ                   ║",
            "╠═══════════════════════════════════════════╣",
            "║  Управление:                             ║",
            "║  • Стрелки - движение                    ║",
            "║  • Пробел - выстрел                      ║",
            "║  • Tab - смена оружия                    ║",
            "║  • P - пауза                             ║",
            "║  • Esc - выход в меню                    ║",
            "║                                          ║",
            "║  Блоки:                                  ║",
            "║  • █ - металл (неразрушимый)            ║",
            "║  • ▒ - кирпич (разрушаемый)             ║",
            "║  • ♣ - куст (укрытие)                   ║",
            "║                                          ║",
            "║  Цель игры:                             ║",
            "║  Защитить свой флаг и уничтожить        ║",
            "║  всех вражеских танков                  ║",
            "║                                          ║",
            "║  Нажмите любую клавишу для возврата     ║",
            "╚═══════════════════════════════════════════╝"
        ]

        self.screen.clear()
        h, w = self.screen.getmaxyx()
        
        for i, line in enumerate(instructions):
            x = w//2 - len(line)//2
            y = h//2 - len(instructions)//2 + i
            self.screen.addstr(y, x, line, curses.color_pair(1))

        self.screen.refresh()
        self.screen.getch()

    def show_game_hud(self, player: PlayerTank, level: int, 
                     killed_tanks: int, time_elapsed: float) -> None:
        """Отображение игрового HUD"""
        h, w = self.screen.getmaxyx()
        
        # Верхняя панель
        hud_info = [
            f"Уровень: {level}",
            f"Жизни: {'♥' * player.lives}",
            f"Счет: {player.score}",
            f"Убито танков: {killed_tanks}",
            f"Время: {int(time_elapsed)}с",
            f"Оружие: {player.current_weapon}"
        ]

        for i, info in enumerate(hud_info):
            self.screen.addstr(0, i * 20, info, curses.color_pair(1))

    def show_pause_menu(self) -> str:
        """Отображение меню паузы"""
        pause_menu = [
            "╔═══════════════════════════════╗",
            "║            ПАУЗА              ║",
            "╠═══════════════════════════════╣",
            "║  1. Продолжить                ║",
            "║  2. Начать заново             ║",
            "║  3. Выйти в главное меню      ║",
            "╚═══════════════════════════════╝"
        ]

        while True:
            self.screen.clear()
            h, w = self.screen.getmaxyx()
            
            for i, item in enumerate(pause_menu):
                x = w//2 - len(item)//2
                y = h//2 - len(pause_menu)//2 + i
                self.screen.addstr(y, x, item, curses.color_pair(1))

            self.screen.refresh()
            
            key = self.screen.getch()
            if key in [ord('1'), ord('2'), ord('3')]:
                return str(chr(key))

    def show_game_over(self, stats: Dict) -> str:
        """Отображение экрана окончания игры"""
        game_over = [
            "╔═══════════════════════════════╗",
            "║          GAME OVER            ║", "╠═══════════════════════════════╣",
            f"║  Уровень: {stats['level']}         ║",
            f"║  Счет: {stats['score']}          ║",
            f"║  Убито танков: {stats['killed_tanks']}  ║",
            f"║  Время: {stats['time_elapsed']}с    ║",
            "║                                          ║",
            "║  1. Начать заново                ║",
            "║  2. Выйти в главное меню        ║",
            "╚═══════════════════════════════╝"
        ]

        while True:
            self.screen.clear()
            h, w = self.screen.getmaxyx()
            
            for i, item in enumerate(game_over):
                x = w//2 - len(item)//2
                y = h//2 - len(game_over)//2 + i
                self.screen.addstr(y, x, item, curses.color_pair(1))

            self.screen.refresh()
            
            key = self.screen.getch()
            if key in [ord('1'), ord('2')]:
                return str(chr(key))

def main(screen):
    """Основная функция игры"""
    curses.curs_set(0)  # Скрыть курсор
    screen.nodelay(1)  # Не блокировать ввод
    screen.timeout(100)  # Обновление экрана каждые 100 мс

    ui = UserInterface(screen)
    game_state = "MENU"
    level = 1
    player = None
    game_map = None

    while True:
        if game_state == "MENU":
            choice = ui.show_main_menu()
            if choice == '1':
                level = 1
                game_state = "LEVEL_SELECTION"
            elif choice == '2':
                level = ui.show_level_selection()
                game_state = "START_GAME"
            elif choice == '3':
                ui.show_instructions()
            elif choice == '4':
                break  # Выход из игры

        elif game_state == "LEVEL_SELECTION":
            level = ui.show_level_selection()
            game_state = "START_GAME"

        elif game_state == "START_GAME":
            game_map = GameMap(20, 10, level)
            game_map.initialize_level()
            player = game_map.player
            start_time = time.time()
            game_state = "PLAYING"

        elif game_state == "PLAYING":
            current_time = time.time() - start_time
            ui.show_game_hud(player, level, game_map.killed_tanks, current_time)

            game_map.update(current_time)
            game_map.render(screen)

            key = screen.getch()
            if key == ord(' '):  # Выстрел
                player.shoot(current_time)
            elif key == curses.KEY_UP or key == curses.KEY_DOWN or key == curses.KEY_LEFT or key == curses.KEY_RIGHT:
                player.update(game_map)
            elif key == ord('p'):  # Пауза
                game_state = "PAUSED"

            if player.lives <= 0:
                game_state = "GAME_OVER"

        elif game_state == "PAUSED":
            choice = ui.show_pause_menu()
            if choice == '1':
                game_state = "PLAYING"
            elif choice == '2':
                level = 1
                game_state = "START_GAME"
            elif choice == '3':
                game_state = "MENU"

        elif game_state == "GAME_OVER":
            stats = {
                'level': level,
                'score': player.score,
                'killed_tanks': game_map.killed_tanks,
                'time_elapsed': int(current_time)
            }
            choice = ui.show_game_over(stats)
            if choice == '1':
                level = 1
                game_state = "START_GAME"
            elif choice == '2':
                game_state = "MENU"

if __name__ == "__main__":
    curses.wrapper(main)