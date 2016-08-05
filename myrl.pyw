import libtcodpy as libtcod
import math
import textwrap
import shelve

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
INVENTORY_WIDTH = 50
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

color_dark_wall = libtcod.Color(100, 0, 0)
color_light_wall = libtcod.Color(200, 0, 0)
color_dark_ground = libtcod.Color(150, 50, 50)
color_light_ground =libtcod.Color(250, 50, 50)

LIMIT_FPS = 20

MAP_WIDTH = 80
MAP_HEIGHT = 43

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

HEAL_AMOUNT = 10
LIGHTNING_DAMAGE = 12
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 7


class Tile:
	#a tile of the map and its properties
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked
		self.explored = False

		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight

class Object:
	def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None, equipment=None):
		self.x = x
		self.y = y
		self.char = char
		self.name = name
		self.color = color
		self.blocks = blocks
		self.always_visible = always_visible
		
		self.fighter = fighter
		if self.fighter:
			self.fighter.owner = self
			
		self.ai = ai
		if self.ai:
			self.ai.owner = self
		
		self.item = item
		if self.item:
			self.item.owner = self
		
		self.equipment = equipment
		if self.equipment:
			self.equipment.owner = self
			self.item = Item()
			self.item.owner = self
		
	def move(self, dx, dy):
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy
	
	def move_towards(self, target_x, target_y):
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)
		
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)
		
	def distance_to(self, other):
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)
		
	def distance(self, x, y):
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
		
	def draw(self):
		if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or
			(self.always_visible and map[self.x][self.y].explored)):
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
		
	def clear(self):
		libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
	
	def send_to_back(self):
		global objects
		objects.remove(self)
		objects.insert(0, self)

class Item:
	def __init__(self, use_function=None):
		self.use_function = use_function
	
	def use(self):
		if self.owner.equipment:
			self.owner.equipment.toggle_equip()
			return
		if self.use_function is None:
			message('The ' + self.owner.name + ' cannot be used.')
		else:
			if self.use_function() != 'cancelled':
				inventory.remove(self.owner)
	
	def pick_up(self):
		if len(inventory) >= 26:
			message('Your inventory is full; cannot pick up the ' + self.owner.name + '.', libtcod.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			message('You picked up a ' + self.owner.name + '!', libtcod.green)
	
	def drop(self):
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player. y
		if self.owner.equipment:
			self.owner.equipment.dequip()
		message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
		
class Equipment:
	def __init__(self, slot, power_bonus=0, defense_bonus=0, dexterity_bonus=0, max_hp_bonus=0):
		self.slot = slot
		self.is_equipped = False
		self.power_bonus = power_bonus
		self.defense_bonus = defense_bonus
		self.dexterity_bonus = dexterity_bonus
		self.max_hp_bonus = max_hp_bonus
	
	def toggle_equip(self):
		if self.is_equipped:
			self.dequip()
		else:
			self.equip()
	
	def equip(self):
		old_equipment = get_equipped_in_slot(self.slot)
		if old_equipment is not None:
			old_equipment.dequip()
		self.is_equipped = True
		message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)
		
	def dequip(self):
		if not self.is_equipped: return
		self.is_equipped = False
		message('Dequipped ' + self.owner.name + ' off ' + self.slot + '.', libtcod.light_yellow)

def get_equipped_in_slot(slot):
	for obj in inventory:
		if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
			return obj.equipment
	return None
		
class Fighter:
	def __init__(self, hp, dexterity, power, xp, death_function=None):
		self.base_max_hp = hp
		self.hp = hp
		self.base_dexterity = dexterity
		self.base_power = power
		self.xp = xp
		self.death_function = death_function
	
	@property
	def power(self):
		bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
		return self.base_power + bonus
		
	@property
	def dexterity(self):
		bonus = sum(equipment.dexterity_bonus for equipment in get_all_equipped(self.owner))
		return self.base_dexterity + bonus
	
	@property
	def defense(self):
		bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
		return self.base_dexterity + bonus
		
	@property
	def max_hp(self):
		bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
		return self.base_max_hp + bonus
	
	def take_damage(self, damage):
		if damage > 0:
			self.hp -= damage
		if self.hp <= 0:
			function = self.death_function
			if function is not None:
				function(self.owner)
			if self.owner != player:
				player.fighter.xp += self.xp
		
	def heal(self, amount):
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp
	
	def attack(self, target):
		roll = roll_skill_dice()
		off_mod = self.dexterity
		def_mod = target.fighter.defense
		
		flanking_penalty = adjacent_monsters() - 1		#-1 because there will (hopefully) always be at least on adjacent enemy, resulting in 0
		if self.owner == player:
			off_mod -= flanking_penalty
		elif target == player:
			def_mod -= flanking_penalty
			
		sum = off_mod - def_mod + roll
		hits =  sum >= 0
		damage = self.power
		attack_string = ( self.owner.name.capitalize() + ' attacks ' + target.name + ': ' +
				str(roll) + '+' + str(off_mod) +  '-' + str(def_mod) + '=' + str(sum) + ': ' )
		if hits:
			message( attack_string + 'Hit for ' + str(damage) + ' damage.' )
			target.fighter.take_damage(damage)
		else:
			message( attack_string + 'Miss!' )

def get_all_equipped(obj):
	if obj == player:
		equipped_list = []
		for item in inventory:
			if item.equipment and item.equipment.is_equipped:
				equipped_list.append(item.equipment)
		return equipped_list
	else:
		return []
			
class BasicMonster:
	def __init__(self):
		self.target = None
		self.path = None
		
	def take_turn(self):
		monster = self.owner
		
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			self.target = (player.x, player.y)
		
		if self.target:
			clogged_coords = []
			for obj in objects:
				if obj.blocks and not ( obj == monster or obj == player ):
					clogged_coords.append((obj.x, obj.y))
			self.path = libtcod.path_new_using_function(MAP_WIDTH, MAP_HEIGHT, my_path_func, clogged_coords, 1.0)
			libtcod.path_compute(self.path, monster.x, monster.y, self.target[0], self.target[1])
		
		if self.path and self.target:
			if libtcod.path_is_empty(self.path):
				name = self.owner.name
				article = 'a'
				if name[0] in ['a', 'e', 'i', 'o', 'u', 'y']:
					article += 'n'
				name = article + ' ' + name
				message('You hear the frustrated grunt of ' + name + ' in the distance...', libtcod.yellow)
				libtcod.path_delete(self.path)
				self.path = None
				self.target = None
			elif monster.distance_to(player) < 2 and player.fighter.hp > 0:
				monster.fighter.attack(player)
			elif monster.distance(self.target[0], self.target[1]) > 0:
				x,y=libtcod.path_walk(self.path,True)
				monster.move_towards(x, y)
			else:
				weirdness = 'Weirdness in BasicMonster pathing: ' + self.owner.name + ' (' + str(self.owner.x) + ',' + str(self.owner.y) + ')'
				weirdness = weirdness + ' from ' + str(libtcod.path_get_origin(self.path))
				weirdness = weirdness + ' to ' + str(libtcod.path_get_destination(self.path))
				print(weirdness)
		else:
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))	#Just loitering around...

def my_path_func(x0, y0, x1, y1, clogged_coords):
	if not libtcod.map_is_walkable(fov_map, x1, y1):
		return 0.0
	elif (x1, y1) in clogged_coords:
		return 4.0
	else:
		return 1.0

class ConfusedMonster:
	def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.target = None
		self.path = None
		if self.old_ai.path:
			libtcod.path_delete(self.old_ai.path)
			self.old_ai.path = None
		self.num_turns = num_turns
	
	def take_turn(self):
		if self.num_turns > 0:
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
			self.num_turns -= 1
		
		else:
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)

class ShriekingMonster:
	def __init__(self):
		self.target = None
		self.path = None
	
	def take_turn(self):
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			shriek_target = (player.x, player.y)
			for obj in objects:
				if obj.ai:
					obj.ai.target = shriek_target
			message('The ' + self.owner.name + 'lets out a horrible shriek, alerting all monsters to your presence!', libtcod.red)
			
class Rect:
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h
		
	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)
		
	def intersect(self, other):
		return(self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)

def is_blocked(x, y):
	if map[x][y].blocked:
		return True
	
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True
	
	return False

def create_room(room):
	global map
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y):
	global map
	for x in range(min(x1, x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
	global map
	for y in range(min(y1, y2), max(y1, y2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False

def make_map():
	global map, objects, stairs
	
	objects = [player]

	#fill map with "blocked" tiles
	map = [[ Tile(True)
		for y in range(MAP_HEIGHT) ]
			for x in range(MAP_WIDTH) ]
	
	rooms = []
	num_rooms = 0
	
	for r in range(MAX_ROOMS):
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
		
		new_room = Rect(x, y, w, h)
		
		failed = False
		
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break
		
		if not failed:
			create_room(new_room)
			
			(new_x, new_y) = new_room.center()
			
			if num_rooms == 0:
				player.x = new_x
				player.y = new_y
			
			else:
				(prev_x, prev_y) = rooms[num_rooms-1].center()
				if libtcod.random_get_int(0, 0, 1) == 1:
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)
			
			rooms.append(new_room)
			num_rooms += 1
			place_objects(new_room)
		
	stairs = Object(new_x, new_y, '<', 'stairs', libtcod.white, always_visible=True)
	objects.append(stairs)
	stairs.send_to_back()

def handle_keys():
	global fov_recompute
	global keys

	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
		
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit'  #exit game
	
	if game_state == 'playing':
		#movement keys
		if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
			player_move_or_attack(0, -1)
		elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
			player_move_or_attack(0, 1)		
		elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
			player_move_or_attack(-1, 0)		
		elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
			player_move_or_attack(1, 0)
		elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
			player_move_or_attack(-1, -1)
		elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
			player_move_or_attack(1, -1)
		elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
			player_move_or_attack(-1, 1)
		elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
			player_move_or_attack(1, 1)
		elif key.vk == libtcod.KEY_KP5:
			pass
		else:
			key_char = chr(key.c)
			
			if key_char == 'g':
				for object in objects:
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break
			
			if key_char == 'i':
				chosen_item = inventory_menu('Get item. Key on left to pick up, any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.use()
			
			if key_char == 'd':
				chosen_item = inventory_menu('Press key on left to drop, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.drop()
					
			if key_char == 'c':
				level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
				msgbox('Character info\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
					'\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
					'\nAttack: ' + str(player.fighter.power) + '\nDexterity: ' + str(player.fighter.dexterity), CHARACTER_SCREEN_WIDTH)
					
			if key_char == '<':
				if stairs.x == player.x and stairs.y == player.y:
					next_level()
			
			return 'did-not-take-turn'

def next_level():
	global dungeon_level
	message('You take a moment to rest, and recover your strenght.', libtcod.light_violet)
	player.fighter.heal(player.fighter.max_hp / 2)
	message('After a rare moment of peace, you descend deeper into the monstrous bowels...', libtcod.red)
	dungeon_level += 1
	make_map()
	initialize_fov()
	
def from_dungeon_level(table):
	for (value, level) in reversed(table):
		if dungeon_level >= level:
			return value
	return 0
			
def get_names_under_mouse():
	global mouse
	(x, y) = (mouse.cx, mouse.cy)
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
	names = ', '.join(names)
	return names.capitalize()
	
def target_tile(max_range=None):
	global key, mouse
	while True:
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
		render_all()
		
		(x, y) = (mouse.cx, mouse.cy)
		
		if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
			(max_range is None or player.distance(x, y) <= max_range)):
			return (x, y)
		
		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
			return (None, None)

def target_monster(max_range=None):
	while True:
		(x, y) = target_tile(max_range)
		if x is None: return None
		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj

def render_all():
	global fov_map, color_dark_wall, color_light_wall
	global color_dark_ground, color_light_ground
	global fov_recompute
	
	if fov_recompute:
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
	
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			visible = libtcod.map_is_in_fov(fov_map, x, y)
			wall = map[x][y].block_sight
			if not visible:
				if map[x][y].explored:
					if wall:
						libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET )
					else:
						libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET )
			else:
				if wall:
					libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET )
				else:
					libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET )
				map[x][y].explored = True

	for object in objects:
		if object != player:
			object.draw()
		player.draw()
	
	libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)
	
	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)
	
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.red, libtcod.darker_red)
	render_bar(1, 2, BAR_WIDTH, 'XP', player.fighter.xp, LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR, libtcod.darker_yellow, libtcod.grey)
	
	libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon level ' + str(dungeon_level))
	
	#disp names of objects under mouse
	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
	
	#game log
	y = 1
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y +=1
	
	libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	bar_width = int(float(value) / maximum * total_width)
	
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
	
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
	
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))

def menu(header, options, width):
	if len(options) > 26: raise ValueError('Can not have a menu with more than 26 options.')
	
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0
	height = len(options) + header_height
	
	window = libtcod.console_new(width, height)
	
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
	
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y += 1
		letter_index += 1
	
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
	
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	
	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None
	
def inventory_menu(header):
	if len(inventory) == 0:
		options = ['Inventory is empty']
	else:
		options = []
		for item in inventory:
			text = item.name
			if item.equipment and item.equipment.is_equipped:
				text = text + ' (on ' + item.equipment.slot + ')'
			options.append(text)
	
	index = menu(header, options, INVENTORY_WIDTH)
	if index is None or len(inventory) == 0: return None
	return inventory[index].item
	
def msgbox(text, width=50):
	menu(text, [], width)	#Ah, that Jotaf. Using menu as a sort of "message box"
	
def message(new_msg, color = libtcod.white):
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
	
	for line in new_msg_lines:
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
		
		game_msgs.append( (line, color) )

def random_choice(chances_dict):
		chances = chances_dict.values()
		strings = chances_dict.keys()
		return strings[random_choice_index(chances)]

def random_choice_index(chances):
	dice = libtcod.random_get_int(0, 1, sum(chances))
	
	running_sum = 0
	choice = 0
	for w in chances:
		running_sum += w
		
		if dice <= running_sum:
			return choice
		choice += 1
		
def place_objects(room):
	max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6], [7, 7], [8, 8]])
	
	monster_chances = {}
	monster_chances['goblin'] =		from_dungeon_level([[30, 1], [20, 5], [10, 7]])
	monster_chances['orc'] =		from_dungeon_level([[15, 2], [30, 5]])
	monster_chances['troll'] =		from_dungeon_level([[15, 3], [30, 5], [60, 7]])
	monster_chances['shrieker'] = 4
	
	max_items = 1
	
	item_chances = {}
	item_chances['sword'] =	7
	item_chances['shield'] =	from_dungeon_level([[15, 8]])
	item_chances['heal'] = 35
	item_chances['lightning'] =	from_dungeon_level([[25, 4]])
	item_chances['fireball'] =	from_dungeon_level([[25, 6]])
	item_chances['confuse'] =	from_dungeon_level([[10, 2]])
	
	num_monsters = libtcod.random_get_int(0, 0, max_monsters)
	
	for i in range(num_monsters):
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		if not is_blocked(x, y):
			choice = random_choice(monster_chances)
			if choice == 'orc':
				fighter_component = Fighter(hp=5, dexterity=1, power=2, xp=35, death_function=monster_death)
				ai_component = BasicMonster()
				
				monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green, blocks=True, fighter=fighter_component, ai=ai_component)
			elif choice == 'goblin':
				fighter_component = Fighter(hp=3, dexterity=2, power=1, xp=20, death_function=monster_death)
				ai_component = BasicMonster()
				
				monster = Object(x, y, 'g', 'goblin', libtcod.light_green, blocks=True, fighter=fighter_component, ai=ai_component)
			elif choice == 'shrieker':
				fighter_component = Fighter(hp=1, dexterity=0, power=0, xp=20, death_function=monster_death)
				ai_component = ShriekingMonster()
				
				monster = Object(x, y, 's', 'shrieking growth', libtcod.red, blocks=True, fighter=fighter_component, ai=ai_component)
			elif choice == 'troll':
				fighter_component = Fighter(hp=15, dexterity=2, power=5, xp=80, death_function=monster_death)
				ai_component = BasicMonster()
				
				monster = Object(x, y, 'T', 'troll', libtcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component)
			else:
				print('Anomalous choice in monster placement: ' + choice)
				
			objects.append(monster)
	
	num_items = libtcod.random_get_int(0, 0, max_items)
	
	for i in range(num_items):
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		if not is_blocked(x, y):
			choice = random_choice(item_chances)
			if choice == 'sword':
				equipment_component = Equipment(slot='right hand', power_bonus=2)
				item = Object(x, y, ')', 'sword', libtcod.sky, equipment=equipment_component)
			elif choice == 'shield':
				equipment_component = Equipment(slot='left hand', defense_bonus=2)
				item = Object(x, y, ']', 'shield', libtcod.sky, equipment=equipment_component)
			elif choice == 'heal':
				item_component = Item(use_function=cast_heal)
				item = Object(x, y, '!', 'healing potion', libtcod.violet, item=item_component)
			elif choice == 'lightning':
				item_component = Item(use_function=cast_lightning)
				item = Object(x, y, '#', 'scroll of lightning bolt', libtcod.light_blue, item=item_component)
			elif choice == 'confuse':
				item_component = Item(use_function=cast_confuse)
				item = Object(x, y, '#', 'scroll of confusion', libtcod.light_yellow, item=item_component)
			elif choice == 'fireball':
				item_component = Item(use_function=cast_fireball)
				item = Object(x, y, '#', 'scroll of fireball', libtcod.light_red, item=item_component)
			else:
				print('Anomalous choice in item placement: ' + choice)
				pass
			item.always_visible = True
			objects.append(item)
			item.send_to_back()
	
def player_move_or_attack(dx, dy):
	global fov_recompute
	
	x = player.x + dx
	y = player.y + dy
	
	target = None
	for object in objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break
	
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)
		fov_recompute = True

def roll_skill_dice():
	roll = 0
	flipper = 1
	for i in range(4):
		roll += libtcod.random_get_int(0, 0, 5) * flipper
		flipper = flipper * -1
	return roll

def check_level_up():
	level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
	if player.fighter.xp >= level_up_xp:
		player.level += 1
		player.fighter.xp -= level_up_xp
		message('You are getting tougher! You are now a level ' + str(player.level) + ' ass-kicker!', libtcod.yellow)
		
		choice = None
		while choice == None:
			libtcod.console_flush()
			choice = menu('Level up! Choose a stat to raise:\n',
				['Constitution (+5 HP, from ' + str(player.fighter.base_max_hp) + ')',
				'Strength (+1 attack, from ' + str(player.fighter.base_power) + ')',
				'Agility (+1 dexterity, from ' + str(player.fighter.base_dexterity) + ')'], LEVEL_SCREEN_WIDTH)
		
		if choice == 0:
			player.fighter.base_max_hp += 5
			player.fighter.hp += 5
		elif choice == 1:
			player.fighter.base_power += 1
		elif choice == 2:
			player.fighter.base_dexterity += 1
		
def cast_heal():
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health.', libtcod.red)
		return 'cancelled'
	message('Your wounds start to feel better!', libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)
	
def cast_lightning():
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None:
		message('No enemy is close enough to smite.', libtcod.red)
		return 'cancelled'
	message('A thunderbolt strikes the ' + monster.name + ' for ' + str(LIGHTNING_DAMAGE) + ' hit points of damage.', libtcod.light_blue)
	monster.fighter.take_damage(LIGHTNING_DAMAGE)

def cast_confuse():
	message('Left click an enemy to confuse it, r-click to cancel.', libtcod.light_cyan)
	monster = target_monster(CONFUSE_RANGE)
	if monster is None:	return 'cancelled'
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster
	message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)

def cast_fireball():
	message('Left-click a target tile for the fireball, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()
	if x is None: return 'cancelled'
	message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)
	
	for obj in objects:
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
			message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
			obj.fighter.take_damage(FIREBALL_DAMAGE)
	
def closest_monster(max_range):
	closest_enemy = None
	closest_dist = max_range + 1
	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			dist = player.distance_to(object)
			if dist < closest_dist:
				closest_enemy = object
				closest_dist = dist
	return closest_enemy

def adjacent_monsters():
	monsters = 0
	for object in objects:
		xdist = abs(object.x - player.x)
		ydist = abs(object.y - player.y)
		if object.fighter and not object == player and ydist <= 1 and xdist <= 1:
			monsters += 1
	return monsters

def player_death(player):
	global game_state
	message('You died!', libtcod.red)
	game_state = 'dead'
	player.char = '%'
	player.name = 'remains of ' + player.name
	player.color = libtcod.dark_red

def monster_death(monster):
	message( (monster.name.capitalize() + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.') , libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	if monster.ai.path: libtcod.path_delete(monster.ai.path)
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()

############################
# Menu stuff
############################

def main_menu():
	img = libtcod.image_load('belly.bmp')
	
	while not libtcod.console_is_window_closed():
		libtcod.image_blit_2x(img, 0, 0, 0)
		
		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER,
			'THE BELLY OF SARLACC')
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER,
			'By Tuomas J. Salo, with extensive help from Complete Roguelike Tutorial by Jotaf')
		
		choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)
		
		if choice == 0:
			new_game()
			play_game()
		if choice == 1:
			try:
				load_game()
			except:
				msgbox('\nNo saved game to load.\n', 24)
				continue
			play_game()
		elif choice == 2:
			break

def new_game():
	global player, inventory, game_msgs, game_state, dungeon_level
	fighter_component = Fighter(hp=20, dexterity=1, power=1, xp=0, death_function=player_death)
	player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)
	
	player.level = 1
	dungeon_level = 1
	make_map()
	initialize_fov()
	game_state = 'playing'
	inventory = []
	game_msgs = []
	message('You were eaten... now you must face the evils that inhabit the intestines of the monstrous Sarlacc, and find your way out!', libtcod.red)

def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True
	
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
	
	libtcod.console_clear(con)

def play_game():
	global key, mouse
	
	player_action = None
	mouse = libtcod.Mouse()
	key = libtcod.Key()

	while not libtcod.console_is_window_closed():
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
		render_all()
	
		libtcod.console_flush()
		
		check_level_up()
		
		for object in objects:
			object.clear()
	
		player_action = handle_keys()
		if player_action == 'exit':
			save_game()
			break
	
		if game_state == 'playing' and player_action != 'did-not-take-turn':
			for object in objects:
				if object.ai:
					object.ai.take_turn()

def save_game():
	#Sanitize all monster.ai of c objects... A bit hacky?
	for obj in objects:
		if obj.ai and obj.ai.path:
			libtcod.path_delete(obj.ai.path)
			obj.ai.path = None
			
	file = shelve.open('myrl_savegame', 'n')
	file['map'] = map
	file['objects'] = objects
	file['player_index'] = objects.index(player)
	file['stairs_index'] = objects.index(stairs)
	file['inventory'] = inventory
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file['dungeon_level'] = dungeon_level
	file.close()

def load_game():
	global map, objects, player, stairs, inventory, game_msgs, game_state, dungeon_level
	
	file = shelve.open('myrl_savegame', 'r')
	map = file['map']
	objects = file['objects']
	player = objects[file['player_index']]
	stairs = objects[file['stairs_index']]
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	dungeon_level = file['dungeon_level']
	file.close()
	
	initialize_fov()

	
libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GRAYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Belly of Sarlacc v. 0.1', False)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

libtcod.sys_set_fps(LIMIT_FPS)

main_menu()