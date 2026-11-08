"""极简 Lua 表解析器：支持 return {...} 形式的纯数据表。
支持：字符串(双引号/单引号/长括号)、数字、true/false/nil、
表构造 {k=v, [k]=v, positional}、-- 注释。
位置元素返回为 list（若全为位置元素），否则 dict 并把位置元素放在 _array 键。
"""
import re

class LuaParser:
    def __init__(self, text):
        self.s = text
        self.i = 0
        self.n = len(text)

    def error(self, msg):
        raise ValueError(f"Lua parse error at {self.i}: {msg}: ...{self.s[max(0,self.i-40):self.i+40]!r}")

    def skip(self):
        while self.i < self.n:
            c = self.s[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif self.s.startswith("--", self.i):
                # comment: long comment?
                if self.s.startswith("--[[", self.i):
                    end = self.s.find("]]", self.i + 4)
                    self.i = self.n if end < 0 else end + 2
                else:
                    end = self.s.find("\n", self.i)
                    self.i = self.n if end < 0 else end + 1
            else:
                break

    def peek(self):
        self.skip()
        return self.s[self.i] if self.i < self.n else ""

    def parse(self):
        self.skip()
        if self.s.startswith("return", self.i):
            self.i += 6
        v = self.value()
        return v

    def value(self):
        self.skip()
        c = self.s[self.i]
        if c == "{":
            return self.table()
        if c == '"' or c == "'":
            return self.string()
        if self.s.startswith("[[", self.i):
            end = self.s.find("]]", self.i + 2)
            v = self.s[self.i + 2:end]
            self.i = end + 2
            return v
        if self.s.startswith("true", self.i):
            self.i += 4
            return True
        if self.s.startswith("false", self.i):
            self.i += 5
            return False
        if self.s.startswith("nil", self.i):
            self.i += 3
            return None
        m = re.compile(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?").match(self.s, self.i)
        if m:
            self.i = m.end()
            tok = m.group()
            return float(tok) if ("." in tok or "e" in tok or "E" in tok) else int(tok)
        self.error(f"unexpected char {c!r}")

    def string(self):
        q = self.s[self.i]
        self.i += 1
        out = []
        while self.i < self.n:
            c = self.s[self.i]
            if c == "\\":
                nxt = self.s[self.i + 1]
                mp = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "a": "\a", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
                if nxt in mp:
                    out.append(mp[nxt])
                    self.i += 2
                elif nxt == "u":
                    # \u{XXXX}
                    end = self.s.find("}", self.i)
                    out.append(chr(int(self.s[self.i + 3:end], 16)))
                    self.i = end + 1
                elif nxt.isdigit():
                    j = self.i + 1
                    num = ""
                    while j < self.n and self.s[j].isdigit() and len(num) < 3:
                        num += self.s[j]
                        j += 1
                    out.append(chr(int(num)))
                    self.i = j
                else:
                    out.append(nxt)
                    self.i += 2
            elif c == q:
                self.i += 1
                return "".join(out)
            else:
                out.append(c)
                self.i += 1
        self.error("unterminated string")

    def table(self):
        self.i += 1  # {
        items = {}
        arr = []
        has_key = False
        while True:
            self.skip()
            if self.i >= self.n:
                self.error("unterminated table")
            if self.s[self.i] == "}":
                self.i += 1
                break
            # try key = value
            save = self.i
            key = None
            if self.s[self.i] == "[":
                self.i += 1
                key = self.value()
                self.skip()
                if self.s[self.i] != "]":
                    self.error("expected ]")
                self.i += 1
                self.skip()
                if self.i < self.n and self.s[self.i] == "=":
                    self.i += 1
                else:
                    self.error("expected = after ]key")
            else:
                m = re.compile(r"[A-Za-z_][A-Za-z0-9_]*").match(self.s, self.i)
                if m:
                    j = m.end()
                    k = j
                    while k < self.n and self.s[k] in " \t":
                        k += 1
                    if k < self.n and self.s[k] == "=":
                        key = m.group()
                        self.i = k + 1
            if key is not None:
                has_key = True
                items[key] = self.value()
            else:
                self.i = save
                arr.append(self.value())
            self.skip()
            if self.i < self.n and self.s[self.i] in ",;":
                self.i += 1
        if not has_key:
            return arr
        if arr:
            items["_array"] = arr
        return items

def parse_lua(text):
    return LuaParser(text).parse()
