"""MTF, BWT and inverse-BWT explainer animations for the pyflate slides.

Same examples as the deck: decode 2 0 0 1 with [a b c d]; BWT of banana is
nnbaaa with the original at row 3; inverse BWT jumps 2 5 1 4 0 3.
No titles or captions: the GIFs sit on slides that already have them.

Render: see README.md (PNG frames + build_gif.py + gifsicle)
"""
from manim import *

NAVY = "#1E3A5F"
ACCENT = "#E07A1F"
INK = "#222222"
GREY = "#8A8F98"
CELL = "#EEF1F5"
SANS = "Helvetica Neue"
MONO = "Menlo"

config.background_color = WHITE


def txt(s, size=28, color=INK, font=SANS, weight=NORMAL):
    return Text(s, font=font, font_size=size, color=color, weight=weight)


def cell(ch, side=0.9, size=40, fill=CELL, stroke=NAVY):
    box = Square(side, fill_color=fill, fill_opacity=1, stroke_color=stroke, stroke_width=2)
    ref = txt("a", size, font=MONO).height
    g = txt(ch, size, font=MONO).move_to(box.get_center() + DOWN * ref / 2, aligned_edge=DOWN)
    return VGroup(box, g)



class MTF(Scene):
    def construct(self):

        side, gap = 0.9, 0.25
        x0 = -1.5 * (side + gap)
        slot = lambda i: np.array([x0 + i * (side + gap), 0.1, 0])

        letters = ["a", "b", "c", "d"]
        cells = [cell(ch, side).move_to(slot(i)) for i, ch in enumerate(letters)]
        idx = VGroup(*[txt(str(i), 20, GREY).next_to(slot(i), DOWN, buff=0.55) for i in range(4)])
        list_lbl = txt("list", 24, GREY).next_to(cells[0], LEFT, buff=0.6)

        nums = [2, 0, 0, 1]
        inp = VGroup(*[cell(str(n), 0.7, 30, fill=WHITE, stroke=GREY) for n in nums]).arrange(RIGHT, buff=0.15)
        inp.move_to([0, 1.75, 0])
        inp_lbl = txt("numbers read", 24, GREY).next_to(inp, LEFT, buff=0.6)

        out_lbl = txt("letters out", 24, GREY).move_to([-3.2, -1.75, 0])
        out_slots = [np.array([-1.35 + k * 0.85, -1.75, 0]) for k in range(4)]

        self.play(FadeIn(inp), FadeIn(inp_lbl), *[FadeIn(c) for c in cells], FadeIn(idx), FadeIn(list_lbl), FadeIn(out_lbl))
        self.wait(0.6, frozen_frame=False)

        for k, n in enumerate(nums):
            num = inp[k]
            self.play(num[0].animate.set_stroke(ACCENT, 5), run_time=0.35)
            pick = cells[n]
            self.play(pick[0].animate.set_fill(ACCENT, 0.35), Indicate(idx[n], color=ACCENT), run_time=0.45)
            out = pick[1].copy()
            self.play(out.animate.move_to(out_slots[k], aligned_edge=DOWN), run_time=0.5)
            if n > 0:
                self.play(pick.animate.shift(UP * 1.0), run_time=0.35)
                self.play(*[cells[i].animate.move_to(slot(i + 1)) for i in range(n)], run_time=0.45)
                self.play(pick.animate.move_to(slot(0)), run_time=0.4)
                cells = [pick] + cells[:n] + cells[n + 1:]
            else:
                self.play(Indicate(pick, color=ACCENT, scale_factor=1.15), run_time=0.45)
            self.play(pick[0].animate.set_fill(CELL, 1), num[0].animate.set_stroke(GREY, 2), run_time=0.3)

        self.wait(2.5, frozen_frame=False)


class BWT(Scene):
    def construct(self):

        word = "banana"
        rots = [word[k:] + word[:k] for k in range(6)]
        order = sorted(range(6), key=lambda k: rots[k])  # sorted position -> rotation k

        cw, rh = 0.55, 0.56
        top = 1.35
        row_y = lambda r: top - r * rh
        def row(s):
            g = VGroup(*[txt(ch, 30, font=MONO) for ch in s])
            for j, m in enumerate(g):
                m.move_to([-1.4 + j * cw, -0.1, 0], aligned_edge=DOWN)
            return g

        rows = [row(r).shift(UP * row_y(i)) for i, r in enumerate(rots)]
        lbl = txt("rotations", 22, GREY).next_to(rows[0], LEFT, buff=0.7)
        self.play(LaggedStart(*[FadeIn(r, shift=RIGHT * 0.3) for r in rows], lag_ratio=0.25), FadeIn(lbl), run_time=2.0)
        self.wait(0.4, frozen_frame=False)

        sorted_lbl = txt("sorted", 22, GREY).move_to(lbl)
        self.play(*[rows[k].animate.move_to([rows[k].get_center()[0], row_y(pos), 0]) for pos, k in enumerate(order)],
                  Transform(lbl, sorted_lbl), run_time=1.6)
        rows = [rows[k] for k in order]
        nums = VGroup(*[txt(str(i), 22, GREY).move_to([-2.35, row_y(i), 0]) for i in range(6)])
        self.play(FadeIn(nums), lbl.animate.next_to(nums, LEFT, buff=0.35), run_time=0.5)

        col = SurroundingRectangle(VGroup(*[r[-1] for r in rows]), color=ACCENT, buff=0.12, stroke_width=4)
        self.play(Create(col), *[r[-1].animate.set_color(ACCENT) for r in rows], run_time=0.8)

        L = VGroup(*[r[-1].copy() for r in rows])
        target = VGroup(*[txt(r[-1].text, 40, ACCENT, font=MONO) for r in rows]).arrange(RIGHT, buff=0.12, aligned_edge=DOWN)
        target.move_to([3.7, 0.2, 0])
        self.play(*[Transform(L[i], target[i]) for i in range(6)], run_time=1.2)
        self.play(FadeIn(txt("last column", 22, GREY).next_to(target, UP, buff=0.3)), run_time=0.4)

        orig = SurroundingRectangle(VGroup(rows[3], nums[3]), color=NAVY, buff=0.08, stroke_width=3)
        orig_lbl = txt("row 3 is the original word", 22, NAVY).next_to(target, DOWN, buff=0.45)
        self.play(Create(orig), FadeIn(orig_lbl), run_time=0.8)
        self.wait(0.4, frozen_frame=False)

        self.wait(2.5, frozen_frame=False)


class InverseBWT(Scene):
    def construct(self):

        L = "nnbaaa"
        # T[slot] = position of the slot's letter in L (counting sort of L).
        T = sorted(range(6), key=lambda i: (L[i], i))  # [3, 4, 5, 2, 0, 1]

        rh, top = 0.62, 1.15
        y = lambda r: top - r * rh
        xr, xl, xt = -3.2, -2.0, -0.8
        hdr = VGroup(txt("row", 22, GREY).move_to([xr, top + 0.6, 0]),
                     txt("L", 24, GREY, font=MONO).move_to([xl, top + 0.6, 0]),
                     txt("T[row]", 22, GREY).move_to([xt, top + 0.6, 0]))
        rows_n = VGroup(*[txt(str(r), 26, GREY).move_to([xr, y(r), 0]) for r in range(6)])
        Ls = VGroup(*[cell(L[r], 0.55, 28).move_to([xl, y(r), 0]) for r in range(6)])
        Ts = VGroup(*[txt(str(T[r]), 26, NAVY).move_to([xt, y(r), 0]) for r in range(6)])
        self.play(FadeIn(hdr), FadeIn(rows_n), FadeIn(Ls), FadeIn(Ts), run_time=0.8)

        word_lbl = txt("word so far", 22, GREY).move_to([2.9, 1.5, 0])
        slots = [np.array([1.6 + k * 0.55, 0.75, 0]) for k in range(6)]
        self.play(FadeIn(word_lbl), run_time=0.3)

        cur = 3
        marker = SurroundingRectangle(VGroup(rows_n[cur], Ts[cur]), color=NAVY, buff=0.1, stroke_width=3)
        start = txt("start", 22, NAVY).next_to(marker, LEFT, buff=0.2)
        self.play(Create(marker), FadeIn(start), run_time=0.6)
        self.play(FadeOut(start), run_time=0.2)

        for k in range(6):
            nxt = T[cur]
            self.play(Indicate(Ts[cur], color=ACCENT, scale_factor=1.3), run_time=0.4)
            arrow = CurvedArrow(Ts[cur].get_right() + RIGHT * 0.1, Ts[nxt].get_right() + RIGHT * 0.1,
                                angle=-TAU / 4 if nxt > cur else TAU / 4, color=ACCENT, stroke_width=3)
            new_marker = SurroundingRectangle(VGroup(rows_n[nxt], Ts[nxt]), color=NAVY, buff=0.1, stroke_width=3)
            self.play(Create(arrow), run_time=0.45)
            self.play(Transform(marker, new_marker), FadeOut(arrow), Ls[nxt][0].animate.set_fill(ACCENT, 0.35), run_time=0.45)
            letter = Ls[nxt][1].copy()
            self.play(letter.animate.scale(1.3).move_to(slots[k], aligned_edge=DOWN), run_time=0.45)
            self.play(Ls[nxt][0].animate.set_fill(CELL, 1), run_time=0.2)
            cur = nxt

        done = txt("banana, back again", 26, NAVY).move_to([2.95, -0.2, 0])
        self.play(FadeIn(done), run_time=0.4)
        self.wait(2.5, frozen_frame=False)
