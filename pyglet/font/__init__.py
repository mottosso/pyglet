#!/usr/bin/env python
# ----------------------------------------------------------------------------
# pyglet
# Copyright (c) 2006-2007 Alex Holkner
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions 
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright 
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of the pyglet nor the names of its
#    contributors may be used to endorse or promote products
#    derived from this software without specific prior written
#    permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------

'''Load fonts and render text.

This is a fairly-low level interface to text rendering.  Obtain a font using
`load`::

    from pyglet import font
    arial = font.load('Arial', 14, bold=True, italic=False)

pyglet will load any system-installed fonts.  You can add additional fonts
(for example, from your program resources) using `add_file` or
`add_directory`.

Obtain a list of `Glyph` objects for a string of text using the `Font`
object::

    text = 'Hello, world!'
    glyphs = arial.get_glyphs(text)

The most efficient way to render these glyphs is with a `GlyphString`::

    glyph_string = GlyphString(text, glyphs)
    glyph_string.draw()

There are also a variety of methods in both `Font` and
`GlyphString` to facilitate word-wrapping.

A convenient way to render a string of text is with a `Text`::

    text = Text(font, text)
    text.draw()

See the `pyglet.font.base` module for documentation on the base classes used
by this package.
'''

__docformat__ = 'restructuredtext'
__version__ = '$Id$'

import sys
import os
import math

from pyglet.gl import *
from pyglet import window
from pyglet import image

class GlyphString(object):
    '''An immutable string of glyphs that can be rendered quickly.

    This class is ideal for quickly rendering single or multi-line strings
    of text that use the same font.  To wrap text using a glyph string,
    call `get_break_index` to find the optimal breakpoint for each line,
    the repeatedly call `draw` for each breakpoint.
    '''

    def __init__(self, text, glyphs, x=0, y=0):
        '''Create a glyph string.
        
        The `text` string is used to determine valid breakpoints; all glyphs
        must have already been determined using
        `pyglet.font.base.Font.get_glyphs`.  The string
        will be positioned with the baseline of the left-most glyph at the
        given coordinates.
        
        :Parameters:
            `text` : str or unicode
                String to represent.
            `glyphs` : list of `pyglet.font.base.Glyph`
                Glyphs representing `text`.
            `x` : float
                X coordinate of the left-side bearing of the left-most glyph.
            `y` : float
                Y coordinate of the baseline.

        '''
        # Create an interleaved array in GL_T2F_V3F format and determine
        # state changes required.
        
        lst = []
        texture = None
        self.text = text
        self.states = []
        self.cumulative_advance = [] # for fast post-string breaking
        state_from = 0
        state_length = 0
        for i, glyph in enumerate(glyphs):
            if glyph.owner != texture:
                if state_length:
                    self.states.append((state_from, state_length, texture))
                texture = glyph.owner
                state_from = i
                state_length = 0
            state_length += 1
            lst += [glyph.tex_coords[0][0], glyph.tex_coords[0][1],
                    x + glyph.vertices[0], y + glyph.vertices[1], 0.,
                    glyph.tex_coords[1][0], glyph.tex_coords[1][1],
                    x + glyph.vertices[2], y + glyph.vertices[1], 0.,
                    glyph.tex_coords[2][0], glyph.tex_coords[2][1],
                    x + glyph.vertices[2], y + glyph.vertices[3], 0.,
                    glyph.tex_coords[3][0], glyph.tex_coords[3][1],
                    x + glyph.vertices[0], y + glyph.vertices[3], 0.]
            x += glyph.advance
            self.cumulative_advance.append(x)
        self.states.append((state_from, state_length, texture))

        self.array = (c_float * len(lst))(*lst)
        self.width = x

    def get_break_index(self, from_index, width):
        '''Find a breakpoint within the text for a given width.
        
        Returns a valid breakpoint after `from_index` so that the text
        between `from_index` and the breakpoint fits within `width` pixels.

        This method uses precomputed cumulative glyph widths to give quick
        answer, and so is much faster than 
        `pyglet.font.base.Font.get_glyphs_for_width`.  

        :Parameters:
            `from_index` : int
                Index of text to begin at, or 0 for the beginning of the
                string. 
            `width` : float
                Maximum width to use.

        :rtype: int
        :return: the index of text which will be used as the breakpoint, or
            `from_index` if there is no valid breakpoint.
        '''
        to_index = from_index
        if from_index >= len(self.text):
            return from_index
        if from_index:
            width += self.cumulative_advance[from_index-1]
        for i, (c, w) in enumerate(
                zip(self.text[from_index:], 
                    self.cumulative_advance[from_index:])):
            if w > width:
                return to_index 
            if c == '\n':
                return i + from_index + 1
            elif c in u'\u0020\u200b':
                to_index = i + from_index + 1
        return to_index

    def get_subwidth(self, from_index, to_index):
        '''Return the width of a slice of this string.

        :Parameters:
            `from_index` : int
                The start index of the string to measure.
            `to_index` : int
                The end index (exclusive) of the string to measure.

        :rtype: float
        '''
        width = self.cumulative_advance[to_index-1] 
        if from_index:
            width -= self.cumulative_advance[from_index-1]
        return width

    def draw(self, from_index=0, to_index=None):
        '''Draw a region of the glyph string.
        
        Assumes texture state is enabled.  To enable the texture state::

            from pyglet.gl import *
            glEnable(GL_TEXTURE_2D)

        :Parameters:
            `from_index` : int
                Start index of text to render.
            `to_index` : int
                End index (exclusive) of text to render.

        '''
        if from_index >= len(self.text) or \
           from_index == to_index or \
           not self.text:
            return

        # XXX Safe to assume all required textures will use same blend state I
        # think.  (otherwise move this into loop)
        self.states[0][2].apply_blend_state()

        if from_index:
            glPushMatrix()
            glTranslatef(-self.cumulative_advance[from_index-1], 0, 0)
        if to_index is None:
            to_index = len(self.text)

        glPushClientAttrib(GL_CLIENT_VERTEX_ARRAY_BIT)
        glInterleavedArrays(GL_T2F_V3F, 0, self.array)
        for state_from, state_length, texture in self.states:
            if state_from + state_length < from_index:
                continue
            state_from = max(state_from, from_index)
            state_length = min(state_length, to_index - state_from)
            if state_length <= 0:
                break
            glBindTexture(GL_TEXTURE_2D, texture.id)
            glDrawArrays(GL_QUADS, state_from * 4, state_length * 4)
        glPopClientAttrib()

        if from_index:
            glPopMatrix()

class Text(object):
    '''Simple displayable text.

    This is a convenience class for rendering strings of text.  It takes
    care of caching the vertices so the text can be rendered every frame with
    little performance penalty.

    Text can be word-wrapped by specifying a `width` to wrap into.  If the
    width is not specified, it gives the width of the text as laid out.
    '''

    _layout_width = None  # Width to layout text to
    _text_width = 0       # Calculated width of text
    _text_height = 0      # Calculated height of text (bottom descender to top
                          # ascender)

    _dirty = False        # Flag if require layout

    # Alignment constants

    #: Align the left edge of the text to the given X coordinate.
    LEFT = 'left'
    #: Align the horizontal center of the text to the given X coordinate.
    CENTER = 'center'
    #: Align the right edge of the text to the given X coordinate.
    RIGHT = 'right'
    #: Align the bottom of the descender of the final line of text with the
    #: given Y coordinate.
    BOTTOM = 'bottom'
    #: Align the baseline of the first line of text with the given Y
    #: coordinate.
    BASELINE = 'baseline'
    #: Align the top of the ascender of the first line of text with the given
    #: Y coordinate.
    TOP = 'top'

    _halign = LEFT
    _valign = BASELINE

    def __init__(self, font, text='', x=0, y=0, z=0, color=(1,1,1,1),
            width=None, halign=LEFT, valign=BASELINE):
        '''Create displayable text.

        :Parameters:
            `font` : `Font`
                Font to render the text in.
            `text` : str
                Initial string to render.
            `x` : float
                X coordinate of the left edge of the text.
            `y` : float
                Y coordinate of the baseline of the text.  If the text is
                word-wrapped, this refers to the first line of text.
            `z` : float
                Z coordinate of the text plane.
            `color` : 4-tuple of float
                Color to render the text in.  Alpha values can be specified
                in the fourth component.
            `width` : float
                Width to limit the rendering to. Text will be word-wrapped
                if necessary.
            `halign` : str
                Alignment of the text if it is not as wide as the width
                specified, one of LEFT, CENTER or RIGHT. Defaults to LEFT.
            `valign` : str
                Controls positioning of the text based off the y coordinate.
                One of BASELINE, BOTTOM, CENTER or TOP. Defaults to BASELINE.
        '''
        self._dirty = True
        self.font = font
        self._text = text
        self.color = color
        self.x = x
        self.y = y
        self.leading = 0
        self._layout_width = width
        self._halign = halign
        self._valign = valign

    def _clean(self):
        '''Resolve changed layout'''
        text = self._text + ' '
        glyphs = self.font.get_glyphs(text)
        self._glyph_string = GlyphString(text, glyphs)

        self.lines = []
        i = 0
        if self._layout_width is None:
            self._text_width = 0
            while '\n' in text[i:]:
                end = text.index('\n', i)
                self.lines.append((i, end))
                self._text_width = max(self._text_width, 
                                       self._glyph_string.get_subwidth(i, end))
                i = end + 1
            end = len(text)
            if end != i:
                self.lines.append((i, end))
                self._text_width = max(self._text_width,
                                       self._glyph_string.get_subwidth(i, end))
                                   
        else:
            bp = self._glyph_string.get_break_index(i, self._layout_width)
            while i < len(text) and bp > i:
                if text[bp-1] == '\n':
                    self.lines.append((i, bp - 1))
                else:
                    self.lines.append((i, bp))
                i = bp
                bp = self._glyph_string.get_break_index(i, self._layout_width)
            if i < len(text) - 1:
                self.lines.append((i, len(text)))
            
        self.line_height = self.font.ascent - self.font.descent + self.leading
        self._text_height = self.line_height * len(self.lines)

        self._dirty = False
        
    def draw(self):
        '''Render the text.

        This method makes no assumptions about the projection.  Using the
        default projection set up by pyglet, coordinates refer to window-space
        and the text will be aligned to the window.  Other projections can
        be used to render text into 3D space.

        The OpenGL state is not modified by this method.
        '''
        if self._dirty:
            self._clean()

        y = self.y
        if self._valign == self.BOTTOM:
            y += self.height - self.font.ascent
        elif self._valign == self.CENTER:
            y += self.height // 2 - self.font.ascent
        elif self._valign == self.TOP:
            y -= self.font.ascent

        glPushAttrib(GL_CURRENT_BIT | GL_ENABLE_BIT)
        glEnable(GL_TEXTURE_2D)
        glColor4f(*self.color)
        glPushMatrix()
        glTranslatef(0, y, 0)
        for start, end in self.lines:
            width = self._glyph_string.get_subwidth(start, end)

            x = self.x
            if self._halign == self.RIGHT:
                x += self._layout_width - width
            elif self._halign == self.CENTER:
                x += self._layout_width // 2 - width // 2

            glTranslatef(x, 0, 0)
            self._glyph_string.draw(start, end)
            glTranslatef(-x, -self.line_height, 0)
        glPopMatrix()
        glPopAttrib()

    def _get_width(self):
        if self._dirty:
            self._clean()
        if self._layout_width:
            return self._layout_width
        return self._text_width

    def _set_width(self, width):
        self._layout_width = width
        self._dirty = True

    width = property(_get_width, _set_width, 
        doc='''Width of the text.

        When set, this enables word-wrapping to the specified width.
        Otherwise, the width of the text as it will be rendered can be
        determined.
        
        :type: float
        ''')

    def _get_height(self):
        if self._dirty:
            self._clean()
        return self._text_height

    height = property(_get_height,
        doc='''Height of the text.
        
        This property is the ascent minus the descent of the font, unless
        there is more than one line of word-wrapped text, in which case
        the height takes into account the line leading.  Read-only.

        :type: float
        ''')

    def _set_text(self, text):
        self._text = text
        self._dirty = True

    text = property(lambda self: self._text, _set_text,
        doc='''Text to render.

        The glyph vertices are only recalculated as needed, so multiple
        changes to the text can be performed with no performance penalty.
        
        :type: str
        ''')

    def _set_halign(self, halign):
        self._halign = halign
        self._dirty = True

    halign = property(lambda self: self._halign, _set_halign,
        doc='''Horizontal alignment of the text.

        The text is positioned relative to `x` according to this property,
        which must be one of the alignment constants `LEFT`, `CENTER` or
        `RIGHT`.

        :type: str
        ''')

    def _set_valign(self, valign):
        self._valign = valign
        self._dirty = True

    valign = property(lambda self: self._valign, _set_valign,
        doc='''Vertical alignment of the text.

        The text is positioned relative to `y` according to this property,
        which must be one of the alignment constants `BOTTOM`, `BASELINE` or
        `TOP`.

        :type: str
        ''')

if not getattr(sys, 'is_epydoc', False):
    if sys.platform == 'darwin':
        from pyglet.font.carbon import CarbonFont
        _font_class = CarbonFont
    elif sys.platform == 'win32':
        from pyglet.font.win32 import Win32Font
        _font_class = Win32Font
    else:
        from pyglet.font.freetype import FreeTypeFont
        _font_class = FreeTypeFont

def load(name, size, bold=False, italic=False):
    '''Load a font for rendering.

    :Parameters:
        `name` : str, or list of str
            Font family, for example, "Times New Roman".  If a list of names
            is provided, the first one matching a known font is used.  If no
            font can be matched to the name(s), a default font is used.
        `size` : float
            Size of the font, in points.  The returned font may be an exact
            match or the closest available.
        `bold` : bool
            If True, a bold variant is returned, if one exists for the given
            family and size.
        `italic` : bool
            If True, an italic variant is returned, if one exists for the given
            family and size.

    :rtype: `Font`
    '''
    # Find first matching name
    if type(name) in (tuple, list):
        for n in name:
            if _font_class.have_font(n):
                name = n
                break
        else:
            name = None

    # Locate or create font cache   
    shared_object_space = get_current_context().object_space
    if not hasattr(shared_object_space, 'pyglet_font_font_cache'):
        shared_object_space.pyglet_font_font_cache = {}
    font_cache = shared_object_space.pyglet_font_font_cache

    # Look for font name in font cache
    descriptor = (name, size, bold, italic)
    if descriptor in font_cache:
        return font_cache[descriptor]

    # Not in cache, create from scratch
    font = _font_class(name, size, bold=bold, italic=italic)
    font_cache[descriptor] = font
    return font

def add_file(font):
    '''Add a font to pyglet's search path.

    In order to load a font that is not installed on the system, you must
    call this method to tell pyglet that it exists.  You can supply
    either a filename or any file-like object.

    The font format is platform-dependent, but is typically a TrueType font
    file containing a single font face.  Note that to load this file after
    adding it you must specify the face name to `load`, not the filename.

    :Parameters:
        `font` : str or file
            Filename or file-like object to load fonts from.

    '''
    if type(font) in (str, unicode):
        font = open(font, 'rb')
    if hasattr(font, 'read'):
        font = font.read()
    _font_class.add_font_data(font)


def add_directory(dir):
    '''Add a directory of fonts to pyglet's search path.

    This function simply calls `add_file` for each file with a ``.ttf``
    extension in the given directory.  Subdirectories are not searched.

    :Parameters:
        `dir` : str
            Directory that contains font files.

    '''
    import os
    for file in os.listdir(dir):
        if file[:-4].lower() == '.ttf':
            add_file(file)

