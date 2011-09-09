# Compatibility layer for running Django both in 2.x and 3.x
"""
This module currently provides the following helper symbols
 * bytes (name of byte string type; str in 2.x, bytes in 3.x)
 * b (function converting a string literal to an ASCII byte string;
      can be also used to convert a Unicode string with only ASCII
      characters into a byte string)
 * byte (data type for an individual byte)
 * dictvalues returns the .values() of a dict as a list.
   There is a 2to3 fixer for this, but it conflicts with the .values()
   method in django.db.
"""
import sys

if sys.version_info < (3,0):
    b = bytes = str
    def byte(n):
        return n
    u = unicode
    def next(i):
        return i.next()
    def dictvalues(d):
        return d.values()
else:
    bytes = __builtins__['bytes']
    def b(s):
        if isinstance(s, str):
            return s.encode("ascii")
        elif isinstance(s, bytes):
            return s
        else:
            raise TypeError("Invalid argument %r for b()" % (s,))
    def byte(n):
        # assume n is a Latin-1 string of length 1
        return ord(n)
    u = str
    next = __builtins__['next']
    def dictvalues(d):
        return list(d.values())
