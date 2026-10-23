// app/static/js/avatars.js
// Морски аватари за отзиви без лична снимка (рисувани като SVG, без външни файлове).
// Получава spec {creature, accessory, variant, bg} от /api/reviews/public
// (каталогът и изборът са в app/services/review_persona.py) и връща SVG низ.
// 12 героя x 3 цвята x 5 аксесоара x 10 фона = 1800 комбинации; сървърът избира
// 166 различни от тях. Ключовете на героите/аксесоарите трябва да съвпадат с
// CREATURES/ACCESSORIES в review_persona.py (пази ги unit тест).
(function (root) {
  'use strict';

  var BG = ['#ffd3e6', '#cfe7ff', '#ffe5c2', '#d4f4e2', '#e1e6ff',
            '#fff0c2', '#e8d9ff', '#d1f3f0', '#ffdcd2', '#e2f0c8'];

  function rgb(h) { var n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
  function mix(a, b, t) {
    var x = rgb(a), y = rgb(b);
    return '#' + [0, 1, 2].map(function (i) {
      return ('0' + Math.round(x[i] + (y[i] - x[i]) * t).toString(16)).slice(-2);
    }).join('');
  }
  function tone(c) { return { m: c, l: mix(c, '#ffffff', 0.4), d: mix(c, '#000000', 0.2) }; }

  // Всеки герой: основни цветове на 3-те варианта + рисуваща функция.
  // draw(t) връща { body: svg, f: {x,y,e,[sy],[ns]} лице, h: {x,y,w} глава (за шапка) }.
  var CREATURES = {
    octopus: {
      colors: ['#e0559a', '#8f6be0', '#2fb5a8'],
      draw: function (t) {
        return {
          body: '<g fill="' + t.m + '"><ellipse cx="50" cy="44" rx="25" ry="23"/>' +
            '<rect x="25" y="56" width="10" height="31" rx="5"/><rect x="38" y="60" width="10" height="31" rx="5"/>' +
            '<rect x="52" y="60" width="10" height="31" rx="5"/><rect x="65" y="56" width="10" height="31" rx="5"/></g>' +
            '<ellipse cx="38" cy="30" rx="8" ry="4" fill="' + t.l + '" opacity=".55"/>' +
            '<g fill="' + t.d + '" opacity=".35"><circle cx="30" cy="76" r="2"/><circle cx="43" cy="82" r="2"/><circle cx="57" cy="82" r="2"/><circle cx="70" cy="76" r="2"/></g>',
          f: { x: 50, y: 45, e: 10 }, h: { x: 50, y: 24, w: 40 }
        };
      }
    },
    whale: {
      colors: ['#3d7fd6', '#6c7ae0', '#2aa6b8'],
      draw: function (t) {
        return {
          body: '<path d="M78 56c10-2 14-11 14-16 0 9-6 11-11 11 4 3 8 4 11 4-4 7-10 8-14 5z" fill="' + t.d + '"/>' +
            '<ellipse cx="48" cy="58" rx="32" ry="22" fill="' + t.m + '"/><ellipse cx="46" cy="69" rx="23" ry="10" fill="' + t.l + '"/>' +
            '<ellipse cx="60" cy="66" rx="8" ry="4" fill="' + t.d + '" transform="rotate(25 60 66)"/>' +
            '<path d="M38 36q-1-9-8-12M38 36q1-9 8-12" stroke="' + t.l + '" stroke-width="3" fill="none" stroke-linecap="round"/>',
          f: { x: 38, y: 55, e: 8.5 }, h: { x: 38, y: 39, w: 26 }
        };
      }
    },
    crab: {
      colors: ['#e8523f', '#f08a2b', '#d94f86'],
      draw: function (t) {
        return {
          body: '<g stroke="' + t.d + '" stroke-width="5" stroke-linecap="round"><path d="M30 56L20 42M70 56L80 42"/>' +
            '<path d="M30 74l-6 9M70 74l6 9M40 78l-3 10M60 78l3 10" stroke-width="4"/></g>' +
            '<circle cx="19" cy="37" r="10" fill="' + t.m + '"/><circle cx="81" cy="37" r="10" fill="' + t.m + '"/>' +
            '<path d="M13 33l6 5-6 5zM87 33l-6 5 6 5z" fill="' + t.d + '"/>' +
            '<ellipse cx="50" cy="60" rx="27" ry="19" fill="' + t.m + '"/><ellipse cx="40" cy="52" rx="9" ry="4" fill="' + t.l + '" opacity=".5"/>',
          f: { x: 50, y: 57, e: 10 }, h: { x: 50, y: 45, w: 34 }
        };
      }
    },
    pufferfish: {
      colors: ['#f2b632', '#5fb0e6', '#a98be8'],
      draw: function (t) {
        return {
          body: '<path d="M74 52l17-13v26z" fill="' + t.d + '"/>' +
            '<path d="M38 28l3 7M50 25v8M62 28l-3 7M30 36l5 5M70 36l-5 5" stroke="' + t.d + '" stroke-width="3" stroke-linecap="round"/>' +
            '<circle cx="50" cy="53" r="27" fill="' + t.m + '"/><ellipse cx="50" cy="67" rx="18" ry="10" fill="' + t.l + '"/>' +
            '<ellipse cx="72" cy="58" rx="6" ry="3.5" fill="' + t.d + '" transform="rotate(-30 72 58)"/>',
          f: { x: 47, y: 49, e: 9.5 }, h: { x: 47, y: 28, w: 32 }
        };
      }
    },
    seagull: {
      colors: ['#ffffff', '#e4ebf8', '#fff1d0'],
      draw: function (t) {
        return {
          body: '<ellipse cx="54" cy="72" rx="25" ry="18" fill="' + t.m + '" stroke="' + t.d + '" stroke-width="1.6"/>' +
            '<path d="M60 66q20 2 26 18-18 1-28-10z" fill="#9fb0cf"/>' +
            '<circle cx="46" cy="40" r="19" fill="' + t.m + '" stroke="' + t.d + '" stroke-width="1.6"/>' +
            '<path d="M28 43l-16 5 16 5z" fill="#f59a1c"/>',
          f: { x: 47, y: 38, e: 8 }, h: { x: 46, y: 24, w: 30 }
        };
      }
    },
    starfish: {
      colors: ['#f08a2b', '#e8527f', '#f2c230'],
      draw: function (t) {
        var pts = [], i, a, r;
        for (i = 0; i < 10; i++) {
          a = -Math.PI / 2 + i * Math.PI / 5; r = i % 2 ? 17 : 38;
          pts.push((50 + r * Math.cos(a)).toFixed(1) + ',' + (53 + r * Math.sin(a)).toFixed(1));
        }
        return {
          body: '<polygon points="' + pts.join(' ') + '" fill="' + t.m + '" stroke="' + t.m + '" stroke-width="7" stroke-linejoin="round"/>' +
            '<g fill="' + t.l + '" opacity=".6"><circle cx="50" cy="24" r="2"/><circle cx="50" cy="31" r="1.6"/><circle cx="27" cy="46" r="2"/><circle cx="73" cy="46" r="2"/><circle cx="36" cy="76" r="2"/><circle cx="64" cy="76" r="2"/></g>',
          f: { x: 50, y: 52, e: 9 }, h: { x: 50, y: 30, w: 24 }
        };
      }
    },
    dolphin: {
      colors: ['#4aa3df', '#8d86e8', '#3bbfa0'],
      draw: function (t) {
        return {
          body: '<path d="M60 32q2-13 15-18-3 10 0 20z" fill="' + t.d + '"/>' +
            '<circle cx="46" cy="52" r="26" fill="' + t.m + '"/><ellipse cx="74" cy="60" rx="15" ry="8" fill="' + t.m + '"/>' +
            '<ellipse cx="44" cy="66" rx="22" ry="11" fill="' + t.l + '"/><ellipse cx="72" cy="64" rx="12" ry="4.5" fill="' + t.l + '"/>',
          f: { x: 44, y: 48, e: 9 }, h: { x: 44, y: 30, w: 30 }
        };
      }
    },
    turtle: {
      colors: ['#4caf6e', '#9ac84a', '#3aa6a0'],
      draw: function (t) {
        return {
          body: '<ellipse cx="20" cy="74" rx="9" ry="5" fill="' + t.m + '" transform="rotate(-25 20 74)"/><ellipse cx="80" cy="74" rx="9" ry="5" fill="' + t.m + '" transform="rotate(25 80 74)"/>' +
            '<path d="M17 84a33 28 0 0 1 66 0z" fill="' + t.d + '"/>' +
            '<g fill="' + t.l + '" opacity=".45"><path d="M42 72l8-6 8 6-3 9h-10z"/><path d="M22 80l7-5 5 4-2 5z"/><path d="M78 80l-7-5-5 4 2 5z"/></g>' +
            '<circle cx="50" cy="46" r="19" fill="' + t.m + '"/>',
          f: { x: 50, y: 45, e: 7.8 }, h: { x: 50, y: 30, w: 27 }
        };
      }
    },
    shark: {
      colors: ['#6f8fb8', '#8f9bb3', '#5aa0b8'],
      draw: function (t) {
        return {
          body: '<path d="M62 36l9-20 4 24z" fill="' + t.d + '"/>' +
            '<ellipse cx="50" cy="57" rx="33" ry="26" fill="' + t.m + '"/><ellipse cx="50" cy="71" rx="25" ry="13" fill="' + t.l + '"/>' +
            '<path d="M36 70l3 6 3-6zM44 72l3 6 3-6zM52 72l3 6 3-6zM60 70l3 6 3-6z" fill="#fff"/>',
          f: { x: 48, y: 52, e: 11 }, h: { x: 44, y: 35, w: 32 }
        };
      }
    },
    jellyfish: {
      colors: ['#c87be8', '#4fc3e8', '#f08ab0'],
      draw: function (t) {
        return {
          body: '<g stroke="' + t.l + '" stroke-width="4" fill="none" stroke-linecap="round"><path d="M32 52q-5 10 0 20t0 14"/><path d="M42 52q-5 12 0 22t0 14"/><path d="M52 52q5 12 0 22t0 14"/><path d="M62 52q5 10 0 20t0 14"/><path d="M70 50q4 8 0 16"/></g>' +
            '<path d="M22 53a28 28 0 0 1 56 0z" fill="' + t.m + '"/><ellipse cx="38" cy="32" rx="9" ry="4" fill="' + t.l + '" opacity=".6" transform="rotate(-20 38 32)"/>' +
            '<g fill="' + t.d + '" opacity=".35"><circle cx="30" cy="48" r="2.4"/><circle cx="70" cy="48" r="2.4"/></g>',
          f: { x: 50, y: 42, e: 10 }, h: { x: 50, y: 25, w: 36 }
        };
      }
    },
    seal: {
      colors: ['#8c9bb0', '#b39279', '#6f80a8'],
      draw: function (t) {
        return {
          body: '<ellipse cx="20" cy="78" rx="10" ry="5" fill="' + t.d + '" transform="rotate(-30 20 78)"/><ellipse cx="80" cy="78" rx="10" ry="5" fill="' + t.d + '" transform="rotate(30 80 78)"/>' +
            '<circle cx="50" cy="52" r="28" fill="' + t.m + '"/><ellipse cx="50" cy="64" rx="15" ry="11" fill="' + t.l + '"/>' +
            '<ellipse cx="50" cy="58" rx="4.5" ry="3" fill="#2a2430"/>' +
            '<g fill="' + t.d + '" opacity=".6"><circle cx="40" cy="64" r="1.2"/><circle cx="43" cy="68" r="1.2"/><circle cx="60" cy="64" r="1.2"/><circle cx="57" cy="68" r="1.2"/></g>',
          f: { x: 50, y: 46, e: 11, sy: 19 }, h: { x: 50, y: 27, w: 34 }
        };
      }
    },
    penguin: {
      colors: ['#2f3b52', '#3a4f7a', '#4b3a6e'],
      draw: function (t) {
        return {
          body: '<ellipse cx="24" cy="62" rx="7" ry="16" fill="' + t.d + '" transform="rotate(14 24 62)"/><ellipse cx="76" cy="62" rx="7" ry="16" fill="' + t.d + '" transform="rotate(-14 76 62)"/>' +
            '<ellipse cx="40" cy="90" rx="9" ry="4.5" fill="#f59a1c"/><ellipse cx="60" cy="90" rx="9" ry="4.5" fill="#f59a1c"/>' +
            '<ellipse cx="50" cy="58" rx="26" ry="31" fill="' + t.m + '"/><ellipse cx="50" cy="66" rx="18" ry="23" fill="#f4f6fb"/>' +
            '<path d="M43 50l7 8 7-8z" fill="#f59a1c"/>',
          f: { x: 50, y: 42, e: 8.5, ns: 1 }, h: { x: 50, y: 30, w: 28 }
        };
      }
    }
  };

  function eyes(f) {
    var out = '', s = [-1, 1], i;
    for (i = 0; i < 2; i++) {
      out += '<circle cx="' + (f.x + s[i] * f.e) + '" cy="' + f.y + '" r="4.6" fill="#fff"/>' +
        '<circle cx="' + (f.x + s[i] * f.e + 0.4) + '" cy="' + (f.y + 0.4) + '" r="2.7" fill="#1b1b24"/>' +
        '<circle cx="' + (f.x + s[i] * f.e + 1.2) + '" cy="' + (f.y - 0.6) + '" r="0.9" fill="#fff"/>';
    }
    return out;
  }

  function smile(f) {
    var w = f.e * 0.72, y = f.y + (f.sy || f.e * 1.2);
    return '<path d="M' + (f.x - w) + ' ' + y + 'q' + w + ' ' + w * 0.95 + ' ' + 2 * w + ' 0" fill="none" stroke="#2b1d1d" stroke-width="2.2" stroke-linecap="round"/>';
  }

  var ACCESSORIES = {
    shades: function (f) {
      var k = f.e / 10, x = f.x, y = f.y;
      return '<rect x="' + (x - 19 * k) + '" y="' + (y - 1.4) + '" width="' + 38 * k + '" height="2.4" fill="#14141c"/>' +
        '<ellipse cx="' + (x - 10 * k) + '" cy="' + (y + 2) + '" rx="' + 8.6 * k + '" ry="' + 6.4 * k + '" fill="#14141c"/>' +
        '<ellipse cx="' + (x + 10 * k) + '" cy="' + (y + 2) + '" rx="' + 8.6 * k + '" ry="' + 6.4 * k + '" fill="#14141c"/>' +
        '<path d="M' + (x - 14 * k) + ' ' + y + 'l4 0M' + (x + 6 * k) + ' ' + y + 'l4 0" stroke="#fff" stroke-opacity=".45" stroke-width="1.6" stroke-linecap="round"/>';
    },
    glasses: function (f) {
      var r = f.e * 0.82;
      return '<g fill="#ffffff" fill-opacity=".3" stroke="#2b2f45" stroke-width="2">' +
        '<circle cx="' + (f.x - f.e) + '" cy="' + f.y + '" r="' + r + '"/><circle cx="' + (f.x + f.e) + '" cy="' + f.y + '" r="' + r + '"/></g>' +
        '<path d="M' + (f.x - f.e + r) + ' ' + f.y + 'h' + (2 * f.e - 2 * r) + '" stroke="#2b2f45" stroke-width="2"/>';
    },
    cap: function (f, h) {
      var x = h.x, y = h.y, w = h.w;
      return '<path d="M' + (x - w / 2) + ' ' + (y + 3) + 'Q' + (x - w / 2) + ' ' + (y - w * 0.42) + ' ' + x + ' ' + (y - w * 0.42) +
        'T' + (x + w / 2) + ' ' + (y + 3) + 'Z" fill="#f8fafc" stroke="#c3cddd" stroke-width=".8"/>' +
        '<rect x="' + (x - w / 2) + '" y="' + (y - 1.5) + '" width="' + w + '" height="5.5" fill="#1e3a6e"/>' +
        '<path d="M' + (x - w * 0.4) + ' ' + (y + 4) + 'h' + w * 0.8 + 'q0 5 -' + w * 0.18 + ' 5h-' + w * 0.44 + 'q-' + w * 0.18 + ' 0 -' + w * 0.18 + ' -5z" fill="#0f2540"/>' +
        '<circle cx="' + x + '" cy="' + (y + 1.2) + '" r="2.3" fill="#e8a020"/>';
    },
    bandana: function (f, h) {
      var x = h.x, y = h.y + 2, w = h.w * 0.9, i, dots = '';
      for (i = 0; i < 4; i++) dots += '<circle cx="' + (x - w * 0.36 + i * w * 0.24) + '" cy="' + (y + 3.6) + '" r="1.1" fill="#fff"/>';
      return '<path d="M' + (x - w / 2) + ' ' + y + 'q' + w / 2 + ' -3 ' + w + ' 0v7q-' + w / 2 + ' 3 -' + w + ' 0z" fill="#d63a3a"/>' + dots +
        '<path d="M' + (x + w / 2 - 1) + ' ' + (y + 3) + 'l7 -4 1 9z" fill="#b82c2c"/>';
    },
    headphones: function (f, h) {
      var x = h.x, w = h.w, top = h.y - w * 0.3, ey = f.y - 2;
      return '<path d="M' + (x - w / 2) + ' ' + ey + 'Q' + (x - w / 2) + ' ' + top + ' ' + x + ' ' + top + 'Q' + (x + w / 2) + ' ' + top + ' ' + (x + w / 2) + ' ' + ey +
        '" fill="none" stroke="#2a3350" stroke-width="4" stroke-linecap="round"/>' +
        '<rect x="' + (x - w / 2 - 4) + '" y="' + (ey - 6) + '" width="8" height="15" rx="3.5" fill="#e8a020" stroke="#2a3350" stroke-width="1.6"/>' +
        '<rect x="' + (x + w / 2 - 4) + '" y="' + (ey - 6) + '" width="8" height="15" rx="3.5" fill="#e8a020" stroke="#2a3350" stroke-width="1.6"/>';
    }
  };

  // spec -> SVG низ. cls е CSS клас на <svg> (размерът се задава от CSS).
  function svg(spec, cls) {
    var c = CREATURES[spec.creature] || CREATURES.octopus;
    var acc = ACCESSORIES[spec.accessory] || ACCESSORIES.shades;
    var t = tone(c.colors[spec.variant % c.colors.length]);
    var d = c.draw(t);
    return '<svg class="' + (cls || '') + '" viewBox="0 0 100 100" aria-hidden="true" focusable="false">' +
      '<rect width="100" height="100" fill="' + BG[spec.bg % BG.length] + '"/>' + d.body +
      (spec.accessory === 'shades' ? '' : eyes(d.f)) + (d.f.ns ? '' : smile(d.f)) + acc(d.f, d.h) + '</svg>';
  }

  root.MaritimeAvatars = {
    svg: svg,
    creatures: Object.keys(CREATURES),
    accessories: Object.keys(ACCESSORIES),
    backgrounds: BG.length
  };
})(window);
