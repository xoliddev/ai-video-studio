// Flat clothing illustrations (viewBox 0 0 200 240). Each takes a fill colour and returns SVG markup.
const GARMENTS = (() => {
  const shade = (c, k) => {
    const n = parseInt(c.slice(1), 16), f = v => Math.max(0, Math.min(255, Math.round(v * k)));
    return '#' + [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(f).map(v => v.toString(16).padStart(2, '0')).join('');
  };
  const wrap = (body) => `<svg viewBox="0 0 200 240" xmlns="http://www.w3.org/2000/svg">${body}</svg>`;
  return {
    dress: c => wrap(`
      <path d="M70 20 Q100 42 130 20 L150 28 L170 60 L150 71 L142 58 Q138 95 133 110 L176 224 Q100 240 24 224 L67 110 Q62 95 58 58 L50 71 L30 60 L50 28 Z" fill="${c}"/>
      <path d="M100 112 L133 110 L176 224 Q140 232 104 233 Z" fill="${shade(c, .9)}"/>
      <rect x="66" y="104" width="68" height="11" rx="4" fill="${shade(c, .78)}"/>
      <path d="M88 118 Q84 170 76 228 M112 118 Q118 170 126 228" stroke="${shade(c, .8)}" stroke-width="2.5" fill="none" opacity=".6"/>
      <path d="M70 20 Q100 42 130 20" stroke="${shade(c, .75)}" stroke-width="3" fill="none"/>`),
    tshirt: c => wrap(`
      <path d="M66 22 Q100 40 134 22 L176 42 L192 86 L161 97 L152 76 L153 226 L47 226 L48 76 L39 97 L8 86 L24 42 Z" fill="${c}"/>
      <path d="M100 40 L153 76 L153 226 L104 226 Z" fill="${shade(c, .93)}"/>
      <path d="M66 22 Q100 44 134 22" stroke="${shade(c, .8)}" stroke-width="5" fill="none"/>`),
    hoodie: c => wrap(`
      <path d="M62 30 L138 30 L178 55 L196 182 L172 188 L156 96 L156 228 L44 228 L44 96 L28 188 L4 182 L22 55 Z" fill="${c}"/>
      <path d="M100 50 L156 96 L156 228 L104 228 Z" fill="${shade(c, .92)}"/>
      <path d="M68 30 Q100 -2 132 30 Q118 50 100 52 Q82 50 68 30 Z" fill="${shade(c, .82)}"/>
      <path d="M66 158 L134 158 L144 206 L56 206 Z" fill="${shade(c, .86)}"/>
      <path d="M92 52 L90 92 M108 52 L110 92" stroke="${shade(c, .7)}" stroke-width="3"/>
      <rect x="44" y="216" width="112" height="12" fill="${shade(c, .8)}"/>`),
    jacket: c => wrap(`
      <path d="M62 24 L138 24 L176 50 L194 186 L170 192 L154 96 L156 228 L44 228 L46 96 L30 192 L6 186 L24 50 Z" fill="${c}"/>
      <path d="M100 30 L154 96 L156 228 L101 228 Z" fill="${shade(c, .9)}"/>
      <path d="M62 24 L100 66 L84 30 Z M138 24 L100 66 L116 30 Z" fill="${shade(c, .75)}"/>
      <path d="M100 66 L100 228" stroke="${shade(c, .65)}" stroke-width="3"/>
      <g fill="${shade(c, .55)}"><circle cx="106" cy="98" r="4"/><circle cx="106" cy="134" r="4"/><circle cx="106" cy="170" r="4"/><circle cx="106" cy="206" r="4"/></g>
      <rect x="58" y="96" width="30" height="24" rx="3" fill="none" stroke="${shade(c, .7)}" stroke-width="3"/>
      <rect x="114" y="96" width="30" height="24" rx="3" fill="none" stroke="${shade(c, .7)}" stroke-width="3"/>`),
    pants: c => wrap(`
      <path d="M55 14 L145 14 L161 230 L112 230 L100 84 L88 230 L39 230 Z" fill="${c}"/>
      <path d="M100 84 L145 14 L161 230 L112 230 Z" fill="${shade(c, .9)}"/>
      <rect x="55" y="14" width="90" height="16" fill="${shade(c, .78)}"/>
      <path d="M100 30 L100 80" stroke="${shade(c, .65)}" stroke-width="3"/>`),
    skirt: c => wrap(`
      <path d="M62 34 L138 34 L172 206 Q100 218 28 206 Z" fill="${c}"/>
      <rect x="60" y="26" width="80" height="14" rx="3" fill="${shade(c, .8)}"/>
      <path d="M80 40 L66 210 M100 40 L100 214 M120 40 L134 210 M70 40 L46 207 M130 40 L154 207" stroke="${shade(c, .82)}" stroke-width="3"/>`),
    trench: c => wrap(`
      <path d="M62 20 L138 20 L174 46 L190 190 L168 196 L154 94 L162 232 L38 232 L46 94 L32 196 L10 190 L26 46 Z" fill="${c}"/>
      <path d="M100 26 L154 94 L162 232 L100 232 Z" fill="${shade(c, .9)}"/>
      <path d="M62 20 L94 80 L78 24 Z M138 20 L106 80 L122 24 Z" fill="${shade(c, .78)}"/>
      <rect x="44" y="118" width="114" height="12" fill="${shade(c, .72)}"/>
      <rect x="92" y="114" width="18" height="20" rx="3" fill="none" stroke="${shade(c, .5)}" stroke-width="3"/>
      <g fill="${shade(c, .55)}"><circle cx="84" cy="92" r="4"/><circle cx="116" cy="92" r="4"/><circle cx="84" cy="160" r="4"/><circle cx="116" cy="160" r="4"/></g>`),
    polo: c => wrap(`
      <path d="M66 22 Q100 34 134 22 L176 42 L192 86 L161 97 L152 76 L153 226 L47 226 L48 76 L39 97 L8 86 L24 42 Z" fill="${c}"/>
      <path d="M100 40 L153 76 L153 226 L104 226 Z" fill="${shade(c, .93)}"/>
      <path d="M66 22 L100 44 L84 54 Z M134 22 L100 44 L116 54 Z" fill="${shade(c, .82)}"/>
      <path d="M100 44 L100 92" stroke="${shade(c, .7)}" stroke-width="3"/>
      <g fill="${shade(c, .6)}"><circle cx="104" cy="60" r="3"/><circle cx="104" cy="78" r="3"/></g>`),
  };
})();
