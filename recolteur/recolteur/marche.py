"""Etat de marche d'un actif, alimente par le flux : transactions recentes, carnet, bbo, bougies 5 min, funding prevu."""
import math
from collections import deque
from statistics import median
from . import config as C

def round_sig(x, sig=5):
    if x <= 0: return 0.0
    return round(x, sig - 1 - int(math.floor(math.log10(abs(x)))))

def floor_dec(x, dec):
    f = 10 ** dec
    return math.floor(x * f + 1e-9) / f

class Coin:
    def __init__(self, name, sz_decimals=0):
        self.name, self.szd = name, sz_decimals
        self.trades = deque()                 # (t, px, sz, cote)
        self.bid = self.ask = None; self.bbo_t = None
        self.levels = []; self.book_t = None    # niveaux bid agreges (px, sz)
        self.bars = deque(maxlen=max(C.REGIME_MEDIANE + C.REGIME_BARRES + 5, 60))   # bougies 5 min closes (t, o, h, l, c)
        self.cur = None                       # bougie 5 min en cours
        self.funding = None
        self.since = None                     # debut du flux continu

    # ------------------------------------------------------------ flux
    def on_trade(self, t, px, sz, side):
        if self.since is None: self.since = t
        self.trades.append((t, px, sz, side))
        lim = t - (C.FENETRES_PREC + 1) * C.FENETRE_MS - C.VWAP_DEBUT_MS
        while self.trades and self.trades[0][0] < lim: self.trades.popleft()

    def on_bbo(self, t, bid, ask):
        self.bid, self.ask, self.bbo_t = bid, ask, t

    def on_book(self, t, bids):
        self.levels, self.book_t = bids, t

    def on_candle(self, t, o, h, l, c):
        """Message de bougie en cours ; la precedente est close quand une bougie plus recente arrive."""
        if self.cur is not None and t > self.cur[0]:
            if not self.bars or self.bars[-1][0] < self.cur[0]: self.bars.append(self.cur)
        if self.cur is None or t >= self.cur[0]: self.cur = (t, o, h, l, c)

    def load_bars(self, bars):
        """Amorcage REST : bougies closes (t, o, h, l, c), en ordre croissant."""
        for b in bars:
            if not self.bars or b[0] > self.bars[-1][0]: self.bars.append(tuple(b))

    def reset(self):
        """Trou de flux : l'actif redevient froid, les fenetres sont videes."""
        self.trades.clear(); self.since = None; self.bid = self.ask = self.bbo_t = None; self.levels = []; self.book_t = None

    # ------------------------------------------------------------ mesures
    def mid(self):
        return (self.bid + self.ask) / 2 if self.bid and self.ask else None

    def atr(self):
        b = list(self.bars)[-(C.ATR_N + 1):]
        if len(b) < C.ATR_N + 1: return None
        trs = [max(b[k][2] - b[k][3], abs(b[k][2] - b[k - 1][4]), abs(b[k][3] - b[k - 1][4])) for k in range(1, len(b))]
        return sum(trs) / len(trs)

    def depth(self):
        m = self.mid()
        if m is None: return 0.0
        return sum(px * sz for px, sz in self.levels if px >= m * (1 - C.PROFONDEUR_PCT))

    def ready(self, now):
        return (self.since is not None and now - self.since >= C.CHAUD_MS and self.atr() is not None
                and self.bbo_t is not None and now - self.bbo_t <= C.FRAIS_MS and self.book_t is not None and now - self.book_t <= C.FRAIS_MS)

    def high_60(self, t):
        hi = None
        for tt, px, _, _ in reversed(self.trades):
            if tt < t - C.FENETRE_MS: break
            if tt <= t and (hi is None or px > hi): hi = px
        return hi

    def sell_windows(self, t):
        """Notionnel vendeur agresseur de ]t-60 s, t] et des 20 fenetres de 60 s precedentes."""
        w = [0.0] * (C.FENETRES_PREC + 1)
        for tt, px, sz, side in self.trades:
            if side != "A" or tt > t: continue
            k = int((t - tt) // C.FENETRE_MS)                                    # fenetres ]t-60(k+1), t-60k] : ouvertes a gauche
            if 0 <= k <= C.FENETRES_PREC: w[k] += px * sz
        return w[0], w[1:]

    def vwap(self, t):
        a, b = t - C.VWAP_DEBUT_MS, t - C.VWAP_FIN_MS
        num = den = 0.0
        for tt, px, sz, _ in self.trades:
            if a <= tt <= b: num += px * sz; den += sz
        return num / den if den else None

def btc_regime_ok(bars):
    """Vol 1 h de BTC (12 rendements 5 min) <= 3 x sa mediane sur les 2016 dernieres valeurs."""
    c = [b[4] for b in bars]
    if len(c) < C.REGIME_BARRES + 1 + 100: return None
    r = [math.log(c[k] / c[k - 1]) for k in range(1, len(c))]
    vols = [math.sqrt(sum(x * x for x in r[k - C.REGIME_BARRES:k])) for k in range(C.REGIME_BARRES, len(r) + 1)]
    med = median(vols[-C.REGIME_MEDIANE:])
    return vols[-1] <= C.REGIME_X * med
