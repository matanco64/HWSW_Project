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


class TwoChains(Scene):
    """Inverse BWT from both ends: T forward and its inverse backward, both from row 3."""

    def construct(self):
        L = "nnbaaa"
        T = sorted(range(6), key=lambda i: (L[i], i))      # [3, 4, 5, 2, 0, 1]
        LF = [0] * 6                                         # inverse of T
        for slot, i in enumerate(T):
            LF[i] = slot
        fwd, x = [], 3                                       # forward: jump, then read
        for _ in range(6):
            x = T[x]
            fwd.append(x)
        bwd, x = [], 3                                       # backward: read, then jump
        for _ in range(3):
            bwd.append(x)
            x = LF[x]
        assert "".join(L[r] for r in fwd) == "banana"
        assert "".join(L[r] for r in bwd) == "ana"           # banana from the end

        rh, top = 0.62, 1.55
        y = lambda r: top - r * rh
        xr, xl = -5.6, -4.6
        hdr = VGroup(txt("row", 22, GREY).move_to([xr, top + 0.6, 0]),
                     txt("L", 24, GREY, font=MONO).move_to([xl, top + 0.6, 0]))
        rows_n = VGroup(*[txt(str(r), 26, GREY).move_to([xr, y(r), 0]) for r in range(6)])
        Ls = VGroup(*[cell(L[r], 0.55, 28).move_to([xl, y(r), 0]) for r in range(6)])

        key_f = VGroup(Square(0.28, color=NAVY, stroke_width=4), txt("forward: follow T", 22, NAVY)).arrange(RIGHT, buff=0.15)
        key_b = VGroup(Square(0.28, color=ACCENT, stroke_width=4), txt("backward: follow the inverse of T", 22, ACCENT)).arrange(RIGHT, buff=0.15)
        keys = VGroup(key_f, key_b).arrange(DOWN, aligned_edge=LEFT, buff=0.18).move_to([-4.3, -2.75, 0])

        x0, sw = -1.0, 0.75
        slot = lambda row_y, k: np.array([x0 + k * sw, row_y, 0])
        y1, y2 = 1.2, -0.9
        def slots(row_y):
            return VGroup(*[Square(0.62, stroke_color=GREY, stroke_width=2).move_to(slot(row_y, k)) for k in range(6)])
        s1, s2 = slots(y1), slots(y2)
        lab1 = txt("one chain", 26).next_to(s1, UP, buff=0.25, aligned_edge=LEFT)
        lab2 = txt("two chains", 26).next_to(s2, UP, buff=0.25, aligned_edge=LEFT)
        rnd = txt("round 0", 26, GREY).move_to([3.4, y1 + 0.72, 0])

        self.play(FadeIn(hdr), FadeIn(rows_n), FadeIn(Ls), FadeIn(keys), FadeIn(s1), FadeIn(s2),
                  FadeIn(lab1), FadeIn(lab2), FadeIn(rnd), run_time=0.8)

        mark = lambda r, c: SurroundingRectangle(VGroup(rows_n[r], Ls[r]), color=c, buff=0.1, stroke_width=4)
        mf, mb = mark(3, NAVY), mark(3, ACCENT).scale(1.12)
        start = txt("start", 22, INK).next_to(mf, LEFT, buff=0.25)
        self.play(Create(mf), Create(mb), FadeIn(start), run_time=0.6)
        self.wait(0.3, frozen_frame=False)
        self.play(FadeOut(start), run_time=0.2)

        def put(letter_cell, target, color):
            g = txt(letter_cell[1].text, 34, color, font=MONO)
            g.move_to(letter_cell[1].get_center())
            return g, g.animate.move_to(target.get_center() + DOWN * 0.14, aligned_edge=DOWN)

        for k in range(6):
            new_rnd = txt(f"round {k + 1}", 26, INK).move_to(rnd)
            anims = [Transform(rnd, new_rnd), Transform(mf, mark(fwd[k], NAVY))]
            if k < 3 and k > 0:
                anims.append(Transform(mb, mark(bwd[k], ACCENT).scale(1.12)))
            self.play(*anims, run_time=0.45)
            flies, objs = [], []
            g, a = put(Ls[fwd[k]], s1[k], NAVY); objs.append(g); flies.append(a)
            if k < 3:
                g, a = put(Ls[fwd[k]], s2[k], NAVY); objs.append(g); flies.append(a)
                g, a = put(Ls[bwd[k]], s2[5 - k], ACCENT); objs.append(g); flies.append(a)
            self.add(*objs)
            self.play(*flies, run_time=0.55)
            if k == 2:
                done = txt("done after 3 rounds", 24, ACCENT).next_to(s2, DOWN, buff=0.3)
                self.play(FadeIn(done), FadeOut(mb), run_time=0.4)
        done1 = txt("6 rounds, each waits for the last", 24, NAVY).next_to(s1, DOWN, buff=0.3)
        self.play(FadeIn(done1), run_time=0.4)
        self.wait(2.5, frozen_frame=False)


class Huffman(Scene):
    """Decode the same bits twice: scan the code list (original) vs one table read (shipped)."""

    def construct(self):
        codes = [("00", "a"), ("01", "b"), ("10", "c"), ("110", "d"), ("111", "e")]
        bits = "1100010111"                                   # d a c e
        PB = 3                                                # pyflate peeks 11 bits

        bw = 0.5
        bx0 = -2.9
        bit_cells = VGroup(*[cell(b, 0.46, 26, fill=WHITE, stroke=GREY).move_to([bx0 + i * bw, 2.75, 0])
                             for i, b in enumerate(bits)])
        bits_lbl = txt("bits", 24, GREY).next_to(bit_cells, LEFT, buff=0.4)
        out_lbl = txt("symbols out", 24, GREY).move_to([-3.75, 1.85, 0])
        out_x0 = -2.25
        self.play(FadeIn(bit_cells), FadeIn(bits_lbl), FadeIn(out_lbl), run_time=0.6)

        def window(pos, n):
            return SurroundingRectangle(bit_cells[pos:pos + n], color=ACCENT, buff=0.05, stroke_width=4)

        def run(part_title, panel, step, count_word):
            title_m = txt(part_title, 28, NAVY, weight=BOLD).move_to([0, 1.1, 0])
            counter = txt(f"{count_word}: 0", 26, INK).move_to([2.4, -0.6, 0], aligned_edge=LEFT)
            self.play(FadeIn(title_m), FadeIn(panel), FadeIn(counter), run_time=0.6)
            pos, n_out, total, outs = 0, 0, 0, []
            win = None
            while pos < len(bits):
                pos, sym, total, win, counter = step(pos, total, win, counter)
                o = txt(sym, 34, font=MONO).move_to([out_x0 + n_out * 0.6, 1.72, 0], aligned_edge=DOWN)
                outs.append(o)
                self.play(FadeIn(o, shift=UP * 0.2), run_time=0.3)
                n_out += 1
            self.wait(1.2, frozen_frame=False)
            totals.append(total)
            return VGroup(title_m, panel, counter, *outs, *([win] if win else []))

        totals = []

        def consume(pos, n):
            return [bit_cells[i].animate.set_opacity(0.25) for i in range(pos, pos + n)]

        # ---- original: scan the code list, one check (a method call) per entry
        rows = VGroup(*[VGroup(txt(c, 28, font=MONO), txt(s, 28, font=MONO)) for c, s in codes])
        for j, r in enumerate(rows):                         # fixed columns, shared baseline
            base = -0.55 - j * 0.48
            r[0].move_to([-2.1, base, 0], aligned_edge=DOWN + LEFT)
            r[1].move_to([0.0, base, 0], aligned_edge=DOWN)
        list_hdr = VGroup(txt("code", 20, GREY).move_to([-2.1, -0.05, 0], aligned_edge=LEFT),
                          txt("symbol", 20, GREY).move_to([0.0, -0.05, 0]))
        panel_a = VGroup(rows, list_hdr)

        def scan_step(pos, total, win, counter):
            for j, (c, s) in enumerate(codes):
                total += 1
                cur = SurroundingRectangle(rows[j], color=NAVY, buff=0.08, stroke_width=3)
                new_win = window(pos, len(c))
                new_counter = txt(f"checks: {total}", 26, INK).move_to(counter, aligned_edge=LEFT)
                anims = [Transform(counter, new_counter)]
                anims.append(Transform(win, new_win) if win else Create(new_win))
                if win is None:
                    win = new_win
                self.play(Create(cur), *anims, run_time=0.28)
                if bits[pos:pos + len(c)] == c:
                    self.play(rows[j].animate.set_color(ACCENT), run_time=0.25)
                    self.play(*consume(pos, len(c)), rows[j].animate.set_color(INK), FadeOut(cur), run_time=0.3)
                    return pos + len(c), s, total, win, counter
                self.play(FadeOut(cur), run_time=0.12)
            raise ValueError("no code matched")

        part_a = run("Original: check the code list, one call per entry", panel_a, scan_step, "checks")
        self.play(FadeOut(part_a), *[b.animate.set_opacity(1) for b in bit_cells], run_time=0.6)

        # ---- shipped: peek PB bits, one array index gives symbol and length
        table = []
        for v in range(1 << PB):
            key = format(v, f"0{PB}b")
            c, s = next((c, s) for c, s in codes if key.startswith(c))
            table.append((key, s, len(c)))
        trows = VGroup(*[VGroup(txt(k, 24, font=MONO), txt(s, 24, font=MONO), txt(f"{n} bits", 20, GREY))
                         for k, s, n in table])
        for v, r in enumerate(trows):
            base = -0.45 - v * 0.33
            r[0].move_to([-2.1, base, 0], aligned_edge=DOWN + LEFT)
            r[1].move_to([0.0, base, 0], aligned_edge=DOWN)
            r[2].move_to([0.75, base, 0], aligned_edge=DOWN + LEFT)
        thdr = VGroup(txt(f"next {PB} bits", 20, GREY).move_to([-2.1, 0.0, 0], aligned_edge=LEFT),
                      txt("symbol", 20, GREY).move_to([0.0, 0.0, 0]),
                      txt("uses", 20, GREY).move_to([0.75, 0.0, 0], aligned_edge=LEFT),
                      txt("(pyflate peeks 11 bits)", 18, GREY).move_to([-2.1, -3.25, 0], aligned_edge=LEFT))
        panel_b = VGroup(trows, thdr)

        def table_step(pos, total, win, counter):
            total += 1
            peek = bits[pos:pos + PB].ljust(PB, "0")
            idx = int(peek, 2)
            new_win = window(pos, min(PB, len(bits) - pos))
            new_counter = txt(f"table reads: {total}", 26, INK).move_to(counter, aligned_edge=LEFT)
            anims = [Transform(counter, new_counter), Transform(win, new_win) if win else Create(new_win)]
            if win is None:
                win = new_win
            self.play(*anims, run_time=0.35)
            hit = SurroundingRectangle(trows[idx], color=ACCENT, buff=0.06, stroke_width=4)
            self.play(Create(hit), run_time=0.35)
            n = table[idx][2]
            self.play(*consume(pos, n), FadeOut(hit), run_time=0.35)
            return pos + n, table[idx][1], total, win, counter

        part_b = run("Shipped: one table read per symbol", panel_b, table_step, "table reads")
        cmp_ = VGroup(txt("same 4 symbols:", 24, NAVY),
                      txt(f"{totals[0]} checks vs {totals[1]} reads", 26, NAVY, weight=BOLD)
                      ).arrange(DOWN, aligned_edge=LEFT, buff=0.12).move_to([2.4, -1.6, 0], aligned_edge=LEFT)
        self.play(FadeIn(cmp_, shift=UP * 0.2), run_time=0.5)
        self.wait(2.0, frozen_frame=False)
