/*
 * ui-actions.js — declarative event handlers for templates.
 *
 * Templates must not contain inline JavaScript (CLAUDE.md rule 1). Instead of
 *   onclick="openLoginModal();return false;"
 * an element carries
 *   data-on-click='[["openLoginModal"],["!prevent"]]'
 * and this single delegated listener runs the steps.
 *
 * Supported events: click, input, change, keydown, submit, focus, blur,
 * mouseover, mouseout, mousedown, load, error  (attribute: data-on-<event>).
 *
 * A handler value is a JSON list of steps, executed in order:
 *   ["fnName", arg, ...]            call window.fnName(...args), `this` = element
 *   ["!return", "fnName", arg, ...] call it; if it returns false -> preventDefault
 *   ["!prevent"]                    event.preventDefault()
 *   ["!stop"]                       event.stopPropagation()
 *   ["!ifSelf", "fnName", arg, ...] call only when event.target is the element itself
 *   ["@style", target, prop, value] element.style[prop] = value
 *   ["@class", target, "add"|"remove"|"toggle", className]
 *   ["@removeAttr", target, attrName]
 *   ["@styleData", target, prop, dataKey]  style[prop] = target.dataset[dataKey]
 *   ["!ifKey", "Enter", "fnName", arg, ...] call only for that keyboard key
 *   ["!ifEmpty", "fnName", arg, ...]        call only when element.value is empty
 *   ["!stripSpaces"]                         remove all whitespace from element.value
 *   ["!scaleImage", factor]                  img width = naturalWidth*factor, no max-width
 * target: "$this" or "#elementId".
 * Argument tokens: "$this" (element), "$event", "$value" (element.value),
 * "$src" (element.src), "$target" (event.target),
 * "$data:key" (element.dataset.key — used to pass Jinja values safely),
 * "$num:key" (the same, converted to a Number),
 * "$text:#id" (textContent of that element). Everything else is literal.
 */
(function () {
    'use strict';

    var EVENTS = ['click', 'input', 'change', 'keydown', 'submit', 'focus', 'blur',
                  'mouseover', 'mouseout', 'mousedown', 'load', 'error'];
    // load/error do not bubble: listen in the capture phase and match the target only.
    var TARGET_ONLY = { focus: true, blur: true, load: true, error: true };
    // focus/blur do not bubble; their bubbling twins are used for delegation.
    var LISTEN_AS = { focus: 'focusin', blur: 'focusout' };

    function resolveArg(arg, el, ev) {
        if (typeof arg !== 'string') return arg;
        switch (arg) {
            case '$this': return el;
            case '$event': return ev;
            case '$value': return el.value;
            case '$src': return el.src;
            case '$target': return ev.target;
            default:
                if (arg.indexOf('$data:') === 0) return el.dataset[arg.slice(6)];
                if (arg.indexOf('$num:') === 0) return Number(el.dataset[arg.slice(5)]);
                if (arg.indexOf('$text:#') === 0) {
                    var t = document.getElementById(arg.slice(7));
                    return t ? t.textContent : '';
                }
                return arg;
        }
    }

    function resolveTarget(target, el) {
        if (target === '$this') return el;
        if (typeof target === 'string' && target.charAt(0) === '#') {
            return document.getElementById(target.slice(1));
        }
        return null;
    }

    function callGlobal(name, rawArgs, el, ev) {
        var fn = window[name];
        if (typeof fn !== 'function') {
            console.error('ui-actions: function not found:', name);
            return undefined;
        }
        var args = rawArgs.map(function (a) { return resolveArg(a, el, ev); });
        return fn.apply(el, args);
    }

    function runStep(step, el, ev) {
        var op = step[0];
        switch (op) {
            case '!prevent': ev.preventDefault(); return;
            case '!stop': ev.stopPropagation(); return;
            case '!return':
                if (callGlobal(step[1], step.slice(2), el, ev) === false) ev.preventDefault();
                return;
            case '!ifSelf':
                if (ev.target === el) callGlobal(step[1], step.slice(2), el, ev);
                return;
            case '@style': {
                var t = resolveTarget(step[1], el);
                if (t) t.style[step[2]] = step[3];
                return;
            }
            case '@class': {
                var c = resolveTarget(step[1], el);
                if (c) c.classList[step[2]](step[3]);
                return;
            }
            case '@styleData': {
                var d = resolveTarget(step[1], el);
                if (d) d.style[step[2]] = d.dataset[step[3]];
                return;
            }
            case '!ifKey':
                if (ev.key === step[1]) callGlobal(step[2], step.slice(3), el, ev);
                return;
            case '!ifEmpty':
                if (!el.value) callGlobal(step[1], step.slice(2), el, ev);
                return;
            case '!stripSpaces':
                el.value = el.value.replace(/\s+/g, '');
                return;
            case '!scaleImage':
                el.style.width = (el.naturalWidth * step[1]) + 'px';
                el.style.maxWidth = 'none';
                return;
            case '@removeAttr': {
                var r = resolveTarget(step[1], el);
                if (r) r.removeAttribute(step[2]);
                return;
            }
            default:
                callGlobal(op, step.slice(1), el, ev);
        }
    }

    function runAttr(el, attr, ev) {
        var steps;
        try {
            steps = JSON.parse(el.getAttribute(attr));
        } catch (e) {
            console.error('ui-actions: bad ' + attr + ' value', el);
            return;
        }
        steps.forEach(function (s) { runStep(s, el, ev); });
    }

    // Walks from the event target up to the document, like native bubbling,
    // so nested elements with handlers behave as they did with inline attributes.
    function handle(ev, evName) {
        var attr = 'data-on-' + evName;
        var el = ev.target && ev.target.nodeType === 1 ? ev.target : null;
        // these events fire on the element itself only (as inline handlers did)
        if (TARGET_ONLY[evName]) {
            if (el && el.hasAttribute(attr)) runAttr(el, attr, ev);
            return;
        }
        while (el) {
            if (el.hasAttribute(attr)) {
                runAttr(el, attr, ev);
                if (ev.cancelBubble) return;
            }
            el = el.parentElement;
        }
    }

    EVENTS.forEach(function (evName) {
        document.addEventListener(LISTEN_AS[evName] || evName, function (ev) {
            handle(ev, evName);
        }, !!TARGET_ONLY[evName]);
    });
})();
