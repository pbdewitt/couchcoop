#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
This is sample of how you can implement a tile-based game, not unlike
the RPG games known from consoles, in pygame. It's not a playable game,
but it can be turned into one. Care has been taken to comment it clearly,
so that you can use it easily as a starting point for your game.

The program reads a level definition from a "level.map" file, and uses the
graphics referenced for that file to display a tiled map on the screen and
let you move an animated player character around it.

Note that a lot of additional work is needed to turn it into an actual game.

@copyright: 2008, 2009 Radomir Dopieralski <qq@sheep.art.pl>
@license: BSD, see COPYING for details

"""

import ConfigParser

import pygame
import pygame.locals as pg
from Queue import Queue
from flask import Flask, session, redirect, url_for, escape, request
from threading import Thread

q = Queue()

app = Flask(__name__)

control_page="""
<center>
<h1>
<a href=/up>up</a><br>
<a href=/left>left</a>
<a href=/right>right</a><br>
<a href=/down>down</a>
</h1>
</center>
<br>
<br>
<a href=/quit>quit</a>
"""
@app.route('/')
def landing_page():
    if 'username' in session:
        return control_page
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form['username']
        g.add_player(session['username'])
        return redirect(url_for('landing_page'))
    return '''
        <form method ="post">
            <p><input type=text name=username>
            <p><input type=submit value=Login>
        </form>
    '''
app.secret_key = 'secret2'
@app.route('/quit')
def game_quit():
    global g
    g.game_over =True
    return 'GAME OVER'
def walk(d):
    """Start walking in specified direction."""
    global g

    x, y = g.player.pos
    g.player.direction = d
    if not g.level.is_blocking(x+DX[d], y+DY[d]):
        g.player.animation = g.player.walk_animation()

def do_walk(d):
    try:
        g.players[session['username']].walk(d)
    except KeyError:
        pass
    return redirect(url_for('landing_page'))

@app.route('/up')
def game_up():
    return do_walk(0)
@app.route('/down')
def game_down():
    return do_walk(2)
@app.route('/left')
def game_left():
    return do_walk(3)
@app.route('/right')
def game_right():
    return do_walk(1)
# Motion offsets for particular directions
#     N  E  S   W
DX = [0, 1, 0, -1]
DY = [-1, 0, 1, 0]

# Dimensions of the map tiles
MAP_TILE_WIDTH, MAP_TILE_HEIGHT = 24, 16

class TileCache(object):
    """Load the tilesets lazily into global cache"""

    def __init__(self,  width=32, height=None):
        self.width = width
        self.height = height or width
        self.cache = {}

    def __getitem__(self, filename):
        """Return a table of tiles, load it from disk if needed."""

        key = (filename, self.width, self.height)
        try:
            return self.cache[key]
        except KeyError:
            tile_table = self._load_tile_table(filename, self.width,
                                               self.height)
            self.cache[key] = tile_table
            return tile_table

    def _load_tile_table(self, filename, width, height):
        """Load an image and split it into tiles."""

        image = pygame.image.load(filename).convert()
        image_width, image_height = image.get_size()
        tile_table = []
        for tile_x in range(0, image_width/width):
            line = []
            tile_table.append(line)
            for tile_y in range(0, image_height/height):
                rect = (tile_x*width, tile_y*height, width, height)
                line.append(image.subsurface(rect))
        return tile_table


class SortedUpdates(pygame.sprite.RenderUpdates):
    """A sprite group that sorts them by depth."""

    def sprites(self):
        """The list of sprites in the group, sorted by depth."""

        return sorted(self.spritedict.keys(), key=lambda sprite: sprite.depth)


class Shadow(pygame.sprite.Sprite):
    """Sprite for shadows."""

    def __init__(self, owner):
        pygame.sprite.Sprite.__init__(self)
        self.image = SPRITE_CACHE["shadow.png"][0][0]
        self.image.set_alpha(64)
        self.rect = self.image.get_rect()
        self.owner = owner

    def update(self, *args):
        """Make the shadow follow its owner."""

        self.rect.midbottom = self.owner.rect.midbottom


class Sprite(pygame.sprite.Sprite):
    """Sprite for animated items and base class for Player."""

    is_player = False

    def __init__(self, pos=(0, 0), frames=None):
        super(Sprite, self).__init__()
        if frames:
            self.frames = frames
        self.image = self.frames[0][0]
        self.rect = self.image.get_rect()
        self.animation = self.stand_animation()
        self.pos = pos

    def _get_pos(self):
        """Check the current position of the sprite on the map."""

        return (self.rect.midbottom[0]-12)/24, (self.rect.midbottom[1]-16)/16

    def _set_pos(self, pos):
        """Set the position and depth of the sprite on the map."""

        self.rect.midbottom = pos[0]*24+12, pos[1]*16+16
        self.depth = self.rect.midbottom[1]

    pos = property(_get_pos, _set_pos)

    def move(self, dx, dy):
        """Change the position of the sprite on screen."""

        self.rect.move_ip(dx, dy)
        self.depth = self.rect.midbottom[1]

    def stand_animation(self):
        """The default animation."""

        while True:
            # Change to next frame every two ticks
            for frame in self.frames[0]:
                self.image = frame
                yield None
                yield None

    def update(self, *args):
        """Run the current animation."""

        self.animation.next()


class Player(Sprite):
    """ Display and animate the player character."""

    is_player = True

    def __init__(self, pos=(1, 1)):
        self.frames = SPRITE_CACHE["player.png"]
        Sprite.__init__(self, pos)
        self.direction = 2
        self.animation = None
        self.image = self.frames[self.direction][0]

    def walk_animation(self):
        """Animation for the player walking."""

        # This animation is hardcoded for 4 frames and 16x24 map tiles
        for frame in range(4):
            self.image = self.frames[self.direction][frame]
            yield None
            self.move(3*DX[self.direction], 2*DY[self.direction])
            yield None
            self.move(3*DX[self.direction], 2*DY[self.direction])
    def walk(self, d):
        """Start walking in specified direction."""
        global g

        x, y = self.pos
        self.direction = d
        if not g.level.is_blocking(x+DX[d], y+DY[d]):
            self.animation = self.walk_animation()

    def update(self, *args):
        """Run the current animation or just stand there if no animation set."""

        if self.animation is None:
            self.image = self.frames[self.direction][0]
        else:
            try:
                self.animation.next()
            except StopIteration:
                self.animation = None

class Level(object):
    """Load and store the map of the level, together with all the items."""

    def __init__(self, filename="level.map"):
        self.tileset = ''
        self.map = []
        self.items = {}
        self.key = {}
        self.width = 0
        self.height = 0
        self.load_file(filename)

    def load_file(self, filename="level.map"):
        """Load the level from specified file."""

        parser = ConfigParser.ConfigParser()
        parser.read(filename)
        self.tileset = parser.get("level", "tileset")
        self.map = parser.get("level", "map").split("\n")
        for section in parser.sections():
            if len(section) == 1:
                desc = dict(parser.items(section))
                self.key[section] = desc
        self.width = len(self.map[0])
        self.height = len(self.map)
        for y, line in enumerate(self.map):
            for x, c in enumerate(line):
                if not self.is_wall(x, y) and 'sprite' in self.key[c]:
                    self.items[(x, y)] = self.key[c]

    def render(self):
        """Draw the level on the surface."""

        wall = self.is_wall
        tiles = MAP_CACHE[self.tileset]
        image = pygame.Surface((self.width*MAP_TILE_WIDTH, self.height*MAP_TILE_HEIGHT))
        overlays = {}
        for map_y, line in enumerate(self.map):
            for map_x, c in enumerate(line):
                if wall(map_x, map_y):
                    # Draw different tiles depending on neighbourhood
                    if not wall(map_x, map_y+1):
                        if wall(map_x+1, map_y) and wall(map_x-1, map_y):
                            tile = 1, 2
                        elif wall(map_x+1, map_y):
                            tile = 0, 2
                        elif wall(map_x-1, map_y):
                            tile = 2, 2
                        else:
                            tile = 3, 2
                    else:
                        if wall(map_x+1, map_y+1) and wall(map_x-1, map_y+1):
                            tile = 1, 1
                        elif wall(map_x+1, map_y+1):
                            tile = 0, 1
                        elif wall(map_x-1, map_y+1):
                            tile = 2, 1
                        else:
                            tile = 3, 1
                    # Add overlays if the wall may be obscuring something
                    if not wall(map_x, map_y-1):
                        if wall(map_x+1, map_y) and wall(map_x-1, map_y):
                            over = 1, 0
                        elif wall(map_x+1, map_y):
                            over = 0, 0
                        elif wall(map_x-1, map_y):
                            over = 2, 0
                        else:
                            over = 3, 0
                        overlays[(map_x, map_y)] = tiles[over[0]][over[1]]
                else:
                    try:
                        tile = self.key[c]['tile'].split(',')
                        tile = int(tile[0]), int(tile[1])
                    except (ValueError, KeyError):
                        # Default to ground tile
                        tile = 0, 3
                tile_image = tiles[tile[0]][tile[1]]
                image.blit(tile_image,
                           (map_x*MAP_TILE_WIDTH, map_y*MAP_TILE_HEIGHT))
        return image, overlays

    def get_tile(self, x, y):
        """Tell what's at the specified position of the map."""

        try:
            char = self.map[y][x]
        except IndexError:
            return {}
        try:
            return self.key[char]
        except KeyError:
            return {}

    def get_bool(self, x, y, name):
        """Tell if the specified flag is set for position on the map."""

        value = self.get_tile(x, y).get(name)
        return value in (True, 1, 'true', 'yes', 'True', 'Yes', '1', 'on', 'On')

    def is_wall(self, x, y):
        """Is there a wall?"""

        return self.get_bool(x, y, 'wall')

    def is_blocking(self, x, y):
        """Is this place blocking movement?"""

        if not 0 <= x < self.width or not 0 <= y < self.height:
            return True
        return self.get_bool(x, y, 'block')


class Game(object):
    """The main game object."""

    def __init__(self):
        self.screen = pygame.display.get_surface()
        self.pressed_key = None
        self.game_over = False
        self.shadows = pygame.sprite.RenderUpdates()
        self.sprites = SortedUpdates()
        self.overlays = pygame.sprite.RenderUpdates()
        self.use_level(Level())
        self.players = {}
        sprite = Player(self.level.start_pos)
        self.add_player("player1")

    def add_player(self, name):
        sprite = Player(self.level.start_pos)
        self.players[name] = sprite
        self.sprites.add(sprite)
        self.shadows.add(Shadow(sprite))

    def use_level(self, level):
        """Set the level as the current one."""

        self.shadows = pygame.sprite.RenderUpdates()
        self.sprites = SortedUpdates()
        self.overlays = pygame.sprite.RenderUpdates()
        self.level = level
        # Populate the game with the level's objects
        for pos, tile in level.items.iteritems():
            if tile.get("player") in ('true', '1', 'yes', 'on'):
                level.start_pos = pos
            else:
                sprite = Sprite(pos, SPRITE_CACHE[tile["sprite"]])
            self.sprites.add(sprite)
            self.shadows.add(Shadow(sprite))
        # Render the level map
        self.background, overlays = self.level.render()
        # Add the overlays for the level map
        for (x, y), image in overlays.iteritems():
            overlay = pygame.sprite.Sprite(self.overlays)
            overlay.image = image
            overlay.rect = image.get_rect().move(x*24, y*16-16)

    def control(self):
        """Handle the controls of the game."""

        keys = pygame.key.get_pressed()

        def pressed(key):
            """Check if the specified key is pressed."""

            return self.pressed_key == key or keys[key]
        p = self.players["player1"]


        if pressed(pg.K_UP):
            p.walk(0)
        elif pressed(pg.K_DOWN):
            p.walk(2)
        elif pressed(pg.K_LEFT):
            p.walk(3)
        elif pressed(pg.K_RIGHT):
            p.walk(1)
        self.pressed_key = None

    def main(self):
        """Run the main loop."""

        clock = pygame.time.Clock()
        # Draw the whole screen initially
        self.screen.blit(self.background, (0, 0))
        self.overlays.draw(self.screen)
        pygame.display.flip()
        # The main game loop
        while not self.game_over:
            # Don't clear shadows and overlays, only sprites.
            self.sprites.clear(self.screen, self.background)
            self.sprites.update()
            # If the player's animation is finished, check for keypresses
            for name in self.players:
                p = self.players[name]
                if p.animation is None:
                    self.control()
                    p.update()
            self.shadows.update()
            # Don't add shadows to dirty rectangles, as they already fit inside
            # sprite rectangles.
            self.shadows.draw(self.screen)
            dirty = self.sprites.draw(self.screen)
            # Don't add ovelays to dirty rectangles, only the places where
            # sprites are need to be updated, and those are already dirty.
            self.overlays.draw(self.screen)
            # Update the dirty areas of the screen
            pygame.display.update(dirty)
            # Wait for one tick of the game clock
            clock.tick(30)
            # Process pygame events
            for event in pygame.event.get():
                if event.type == pg.QUIT:
                    self.game_over = True
                elif event.type == pg.KEYDOWN:
                    self.pressed_key = event.key


SPRITE_CACHE = TileCache()
MAP_CACHE = TileCache(MAP_TILE_WIDTH, MAP_TILE_HEIGHT)
TILE_CACHE = TileCache(32, 32)
pygame.init()
pygame.display.set_mode((424, 320))
g = Game()
def run_app():
    return app.run(host='0.0.0.0',port=80)
t = Thread(target=run_app)
t.daemon = True
t.start()
#app.run(threaded=True)
g.main()
