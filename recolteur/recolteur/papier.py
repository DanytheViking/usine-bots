"""Moteur papier de T6 : detection des cascades, ordres ALO simules, sorties, garde-fous, univers, phases.
Pilote uniquement par les evenements du flux et par l'horloge Hyperliquid. Aucun ordre reel."""
import json, os, hashlib, time
from statistics import median
from . import config as C
from .marche import round_sig, floor_dec, btc_regime_ok

def pf_of(trades, mult=1.0):
    rs = [(t["brut"] - t["frais"] * mult - t["funding"]) / t["risque"] for t in trades if t["risque"] > 0]
    pos, neg = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    return (pos / neg if neg > 0 else (float("inf") if pos > 0 else None)), rs

class Moteur:
    def __init__(self, coins, btc, journal, state_path=None, notify=None, fetch_1m=None, wall=time.time):
        self.coins, self.btc, self.j = coins, btc, journal
        self.state_path = state_path or os.path.join(C.DATA_DIR, "etat.json")
        self.notify = notify or (lambda text: None); self.fetch_1m = fetch_1m; self.wall = wall
        self.clock = 0; self._eval = {}
        self.s = {"debut": None, "phase": "mesure", "univers": [], "univers_sha": None, "univers_t": None, "papier_t": None,
                  "profondeur": {}, "dernier_echantillon": 0, "equite": C.CAPITAL, "jour": None, "equite_jour": C.CAPITAL,
                  "pnl_jour": 0.0, "pause_jusqu": 0, "pertes": 0, "gains": 0, "reduit": False, "lignes": {}, "ordres_t": [],
                  "derniere_entree": {}, "dernier_log": {}, "trades": [], "remplissages": 0, "heure_funding": None, "n": 0}
        if os.path.exists(self.state_path):
            self.s.update(json.load(open(self.state_path)))

    # ================================================================ persistance
    def save(self):
        tmp = self.state_path + ".tmp"
        json.dump(self.s, open(tmp, "w"), default=str); os.replace(tmp, self.state_path)

    # ================================================================ evenements du flux
    def on_trade(self, coin, t, px, sz, side, recv_ms=None):
        c = self.coins.get(coin)
        if c is None: return
        self.tick(t)
        if c.since is None: c.since = self.clock                                # la chauffe part de la connexion, pas du lot initial
        c.on_trade(t, px, sz, side)
        for lid, L in list(self.s["lignes"].items()):
            if L["coin"] == coin: self._manage(lid, L, t, px, sz)
        self._detect(c, t, px, recv_ms)

    def on_bbo(self, coin, t, bid, ask):
        c = self.coins.get(coin) or (self.btc if coin == "BTC" else None)
        if c: c.on_bbo(t, bid, ask)
        self.tick(t)

    def on_book(self, coin, t, bids):
        c = self.coins.get(coin)
        if c: c.on_book(t, bids)
        self.tick(t)

    def on_candle(self, coin, t, o, h, l, cl):
        c = self.coins.get(coin) or (self.btc if coin == "BTC" else None)
        if c: c.on_candle(t, o, h, l, cl)

    def on_funding(self, coin, rate):
        c = self.coins.get(coin)
        if c: c.funding = rate

    # ================================================================ lignes ouvertes
    def _manage(self, lid, L, t, px, sz):
        if L["reste"] > 0 and t > L["t_ordre"] and t <= L["expire"] and px < L["limite"]:
            f = min(L["reste"], sz); q0 = L["qty"]
            L["entree"] = (L["entree"] * q0 + L["limite"] * f) / (q0 + f); L["qty"] = q0 + f; L["reste"] = round(L["reste"] - f, 12)
            L["frais"] += f * L["limite"] * C.FEE_MAKER; self.s["remplissages"] += 1
            if L["t_premier"] is None: L["t_premier"] = t
            self.j.record("remplissage", t, ligne=lid, coin=L["coin"], prix=L["limite"], taille=f, reste=L["reste"], stop=L["stop"], stop_arme=True)
        if L["qty"] <= 0: return
        L["haut"], L["bas"] = max(L["haut"], px), min(L["bas"], px)
        if px <= L["stop"]: self._exit(lid, L, px * (1 - C.GLISSEMENT), "STOP", C.FEE_TAKER, t)
        elif px > L["cible"]: self._exit(lid, L, L["cible"], "CIBLE", C.FEE_MAKER, t)

    def _exit(self, lid, L, px, issue, fee, t):
        q = L["qty"]; brut = q * (px - L["entree"]); L["frais"] += q * px * fee
        risque = q * L["stop_dist"]; pnl = brut - L["frais"] - L["funding"]
        tr = {"ligne": lid, "coin": L["coin"], "issue": issue, "entree": L["entree"], "sortie": px, "taille": q, "brut": brut,
              "frais": L["frais"], "funding": L["funding"], "risque": risque, "R": pnl / risque if risque else 0.0,
              "mfe_R": (L["haut"] - L["entree"]) * q / risque if risque else 0.0, "mae_R": (L["bas"] - L["entree"]) * q / risque if risque else 0.0,
              "duree_ms": t - L["t_premier"], "reversion_ms": (t - L["t_premier"]) if issue == "CIBLE" else None,
              "profondeur_obtenue": (L["mid_signal"] - L["entree"]) / L["mid_signal"], "latence_ms": L.get("latence_ms"),
              "t_entree": L["t_premier"], "t_sortie": t, "note": ""}
        self.s["trades"].append(tr); del self.s["lignes"][lid]
        self.s["equite"] += pnl; self.s["pnl_jour"] += pnl
        if pnl < 0:
            self.s["pertes"] += 1; self.s["gains"] = 0
            if self.s["pertes"] >= C.PERTES_REDUIT: self.s["reduit"] = True
        else:
            self.s["gains"] += 1; self.s["pertes"] = 0
            if self.s["reduit"] and self.s["gains"] >= C.GAINS_NORMAL: self.s["reduit"] = False
        self.j.record("sortie", t, **tr, pnl=pnl, equite=self.s["equite"], mode_reduit=self.s["reduit"])
        if self.s["pnl_jour"] <= -C.PERTE_JOUR * self.s["equite_jour"] and self.s["pause_jusqu"] <= t:
            self.s["pause_jusqu"] = t + C.PAUSE_MS
            self.j.record("pause", t, pnl_jour=self.s["pnl_jour"], jusqu=self.s["pause_jusqu"])
            self.notify(f"Pause 12 h : resultat du jour {self.s['pnl_jour']:.2f} USDC (papier)")
        self._check_abandon(t)
        self.save()

    def _check_abandon(self, t):
        n = len(self.s["trades"])
        if self.s["phase"] == "papier" and n >= C.ABANDON_TRADES:
            pf3, _ = pf_of(self.s["trades"], C.STRESS)
            if pf3 is not None and pf3 < C.ABANDON_PF:
                self.s["phase"] = "abandon"
                self.j.record("abandon", t, trades=n, pf_stress=pf3)
                self.notify(f"ABANDON de T6 : PF net {pf3:.2f} (frais x3) apres {n} trades papier, sous 1,2. Plus aucun trade papier.")

    # ================================================================ detection
    def _detect(self, c, t, px, recv_ms):
        if not c.ready(self.clock): return
        hi, a = c.high_60(t), c.atr()
        baisse = hi - px
        if baisse < C.BAISSE_ATR * a: return
        if t - self._eval.get(c.name, -10 ** 15) < C.EVAL_MS: return
        self._eval[c.name] = t
        vend, prec = c.sell_windows(t); med = median(prec)
        if not (vend > 0 and vend >= C.VOLUME_X * med): return
        mid, ask = c.mid(), c.ask
        lim = round_sig(mid - 0.5 * baisse); essais = 0
        while lim >= ask and essais < C.ALO_ESSAIS: lim = round_sig(lim * (1 - C.ALO_RECUL)); essais += 1
        eq = self.s["equite"]; stop_dist = C.STOP_ATR * a
        qty = (eq * C.RISQUE * (0.5 if self.s["reduit"] else 1.0)) / stop_dist
        qty = floor_dec(min(qty, C.NOTIONNEL_MAX * eq / lim) if lim > 0 else 0.0, c.szd)
        notionnel = qty * lim; prof = c.depth(); cible = c.vwap(t)
        complet = prof >= C.PROFONDEUR_X * notionnel and notionnel > 0
        refus = self._refus(c, t, complet, lim, ask, cible, notionnel)
        last = self.s["dernier_log"].get(c.name, -10 ** 15)
        if t - last >= C.CASCADE_LOG_MS:
            self.s["dernier_log"][c.name] = t
            self.j.record("cascade", t, coin=c.name, prix=px, haut_60s=hi, baisse=baisse, atr=a, vendeur_60s=vend, mediane_prec=med,
                          profondeur=prof, notionnel_vise=notionnel, signal_complet=complet, prise=refus is None, refus=refus,
                          latence_ms=(recv_ms - t) if recv_ms else None, note="")
        if refus is None: self._order(c, t, lim, qty, stop_dist, cible, mid, baisse, a, recv_ms)

    def _refus(self, c, t, complet, lim, ask, cible, notionnel):
        s = self.s
        if s["phase"] != "papier": return "phase " + s["phase"]
        if c.name not in s["univers"]: return "hors univers"
        if not complet: return "profondeur insuffisante"
        if t < s["pause_jusqu"]: return "pause journaliere"
        if len(s["lignes"]) >= C.MAX_LIGNES: return "deja 2 lignes"
        if sum(1 for x in s["ordres_t"] if x > t - C.H) >= C.MAX_ORDRES_HEURE: return "6 ordres dans l'heure"
        if t - s["derniere_entree"].get(c.name, -10 ** 15) < C.PAUSE_ACTIF_MS: return "entree recente sur l'actif"
        reg = btc_regime_ok(list(self.btc.bars))
        if reg is None: return "regime BTC indisponible"
        if not reg: return "regime BTC trop volatil"
        if lim >= ask: return "ALO rejete apres 5 essais"
        if cible is None or cible <= lim: return "cible sous l'entree"
        if notionnel < C.NOTIONNEL_MIN: return "taille sous le minimum"
        if notionnel / C.LEVIER > s["equite"]: return "marge insuffisante"
        return None

    def _order(self, c, t, lim, qty, stop_dist, cible, mid, baisse, a, recv_ms):
        s = self.s; s["n"] += 1; lid = f"L{s['n']}"
        s["lignes"][lid] = {"coin": c.name, "limite": lim, "reste": qty, "qty": 0.0, "entree": 0.0, "stop": lim - stop_dist, "stop_dist": stop_dist,
                            "cible": cible, "t_ordre": t, "expire": t + C.EXPIRATION_MS, "t_premier": None, "frais": 0.0, "funding": 0.0,
                            "mid_signal": mid, "baisse": baisse, "haut": lim, "bas": lim, "latence_ms": (recv_ms - t) if recv_ms else None}
        s["ordres_t"] = [x for x in s["ordres_t"] if x > t - C.H] + [t]; s["derniere_entree"][c.name] = t
        self.j.record("ordre", t, ligne=lid, coin=c.name, type="ALO", prix=lim, taille=qty, notionnel=qty * lim, stop=lim - stop_dist, cible=cible,
                      atr=a, mid=mid, levier=C.LEVIER, expiration=t + C.EXPIRATION_MS, mode_reduit=s["reduit"])
        self.save()

    # ================================================================ horloge
    def tick(self, t):
        if t <= self.clock: return
        self.clock = t; s = self.s
        if s["debut"] is None: s["debut"] = t; self.j.record("demarrage_mesure", t, liste=sorted(self.coins))
        day = t // C.D
        if s["jour"] != day:
            if s["jour"] is not None: self._daily(t)
            s["jour"], s["equite_jour"], s["pnl_jour"] = day, s["equite"], 0.0
        for lid, L in list(s["lignes"].items()):
            c = self.coins[L["coin"]]
            if L["reste"] > 0 and t > L["expire"]:
                if L["qty"] <= 0:
                    del s["lignes"][lid]; self.j.record("expire", t, ligne=lid, coin=L["coin"]); continue
                L["reste"] = 0.0; self.j.record("reste_annule", t, ligne=lid, coin=L["coin"], rempli=L["qty"])
            if L["qty"] > 0:
                bid = c.bid or (c.trades[-1][1] if c.trades else L["entree"])
                if t >= L["t_premier"] + C.DUREE_MAX_MS: self._exit(lid, L, bid, "TEMPS", C.FEE_TAKER, t)
                elif c.funding is not None and c.funding > C.FUNDING_SORTIE: self._exit(lid, L, bid, "FUNDING", C.FEE_TAKER, t)
        hour = t // C.H * C.H
        if s["heure_funding"] is None: s["heure_funding"] = hour
        while s["heure_funding"] < hour:
            s["heure_funding"] += C.H
            for L in s["lignes"].values():
                c = self.coins[L["coin"]]
                if L["qty"] > 0 and L["t_premier"] < s["heure_funding"] and c.funding is not None:
                    L["funding"] += c.funding * L["qty"] * (c.mid() or L["entree"])
        if t - s["dernier_echantillon"] >= C.M:
            s["dernier_echantillon"] = t; k = str(day)
            for name, c in self.coins.items():
                if c.mid() and c.book_t is not None and t - c.book_t <= C.FRAIS_MS:
                    d = s["profondeur"].setdefault(name, {}).setdefault(k, [0.0, 0]); d[0] += c.depth(); d[1] += 1
        if s["phase"] == "mesure" and t >= s["debut"] + C.MESURE_MS:
            self._freeze(t); s["phase"], s["papier_t"] = "papier", t
            self.notify(f"Semaine de mesure terminee. Phase papier ouverte sur : {', '.join(s['univers'])}")
        elif s["phase"] == "papier":
            if t >= s["univers_t"] + C.RECLASSEMENT_MS: self._freeze(t)
            if s["remplissages"] >= C.FIN_REMPLISSAGES or t >= s["papier_t"] + C.FIN_PAPIER_MS:
                s["phase"] = "fin"; self.j.record("fin_papier", t, remplissages=s["remplissages"], trades=len(s["trades"]))
                self.notify(f"Phase papier terminee : {len(s['trades'])} trades, {s['remplissages']} remplissages. Rapport : ./installer.sh rapport")

    def ranking(self, t):
        days = {str(d) for d in range((t - C.MESURE_MS) // C.D, t // C.D + 1)}
        mean = {}
        for name, per in self.s["profondeur"].items():
            tot = [v for k, v in per.items() if k in days]; n = sum(v[1] for v in tot)
            if n and name in self.coins: mean[name] = sum(v[0] for v in tot) / n
        return sorted(mean, key=lambda x: -mean[x])[:C.UNIVERS_N], mean

    def _freeze(self, t):
        top, mean = self.ranking(t)
        sha = hashlib.sha256(json.dumps(top).encode()).hexdigest()
        self.s.update(univers=top, univers_sha=sha, univers_t=t)
        self.j.record("univers", t, univers=top, sha256=sha, profondeur_moyenne={k: round(v, 2) for k, v in mean.items()})
        self.save()

    def _daily(self, t):
        s = self.s; tr = [x for x in s["trades"] if x["t_sortie"] >= t - C.D]
        pf1, _ = pf_of(s["trades"]); pf3, _ = pf_of(s["trades"], C.STRESS)
        f = lambda v: "–" if v is None else ("inf" if v == float("inf") else f"{v:.2f}")
        self.notify(f"Bilan du jour : phase {s['phase']}, {len(tr)} trades ({len(s['trades'])} au total), equite papier {s['equite']:.2f} USDC, "
                    f"PF net {f(pf1)} (frais x3 : {f(pf3)}), remplissages {s['remplissages']}")

    # ================================================================ trous de flux
    def gap(self, t_from, t_to):
        """Deconnexion ou redemarrage : ordres annules, positions rejouees sur bougies 1 min, actifs froids."""
        s = self.s
        for lid, L in list(s["lignes"].items()):
            if L["reste"] > 0:
                L["reste"] = 0.0
                if L["qty"] <= 0:
                    del s["lignes"][lid]; self.j.record("annule_trou", t_to, ligne=lid, coin=L["coin"]); continue
            bars = self.fetch_1m(L["coin"], t_from // C.M * C.M, t_to) if self.fetch_1m else []
            for bt, o, h, l, cl in bars:
                end = bt + C.M
                if l <= L["stop"]: self._exit(lid, L, L["stop"] * (1 - C.GLISSEMENT), "STOP", C.FEE_TAKER, end); break
                if h > L["cible"]: self._exit(lid, L, L["cible"], "CIBLE", C.FEE_MAKER, end); break
                if end >= L["t_premier"] + C.DUREE_MAX_MS: self._exit(lid, L, cl, "TEMPS", C.FEE_TAKER, end); break
        for c in list(self.coins.values()) + [self.btc]: c.reset()
        self.j.record("trou", t_to, depuis=t_from, duree_ms=t_to - t_from)
        self.save()

    def status(self):
        s = self.s; j = lambda v: "inf" if v == float("inf") else v
        pf1, pf3 = j(pf_of(s["trades"])[0]), j(pf_of(s["trades"], C.STRESS)[0])
        return {"bot": C.NAME, "version": C.VERSION, "mode": "papier", "t_hl": self.clock, "ts": int(self.wall()), "phase": s["phase"],
                "univers": s["univers"], "lignes": s["lignes"], "trades": len(s["trades"]), "remplissages": s["remplissages"],
                "equite": round(s["equite"], 4), "pf_net": pf1, "pf_stress": pf3, "pause_jusqu": s["pause_jusqu"], "mode_reduit": s["reduit"],
                "prets": sorted(n for n, c in self.coins.items() if c.ready(self.clock))}
