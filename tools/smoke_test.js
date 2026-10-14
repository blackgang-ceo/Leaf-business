/* Runtime smoke test for the LeafBlitz page, run in jsdom WITHOUT any CDN
   resources: this exercises the no-CDN fallback paths (no gsap, no canvas
   raster) plus the estimator + booking + coupon + FAQ flows.

   Usage (needs jsdom):
       cd tools && npm install && node smoke_test.js [path/to/index.html]

   Exit code 0 = every assertion passed. */
const fs = require('fs');
const { JSDOM, VirtualConsole } = require('jsdom');

const path = require('path');
const target = process.argv[2] || path.join(__dirname, '..', 'index.html');
const html = fs.readFileSync(target, 'utf8');

const problems = [];
const notes = [];
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => {
  const msg = String(e.message || e);
  if (msg.includes('Could not parse CSS')) return;          // cssom limitation, browsers are fine
  if (msg.includes('Not implemented: navigation')) { notes.push('navigation attempted (sms: deep link)'); return; }
  if (msg.includes('Not implemented: HTMLCanvasElement')) return;
  problems.push('jsdomError: ' + msg + (e.detail ? ' :: ' + e.detail : ''));
});
vc.on('error', (...a) => problems.push('console.error: ' + a.join(' ')));

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  url: 'https://blackgang-ceo.github.io/Leaf-business/',
  virtualConsole: vc,
  beforeParse(window) {
    // canvas is not implemented in jsdom; absorb all 2d calls.
    window.HTMLCanvasElement.prototype.getContext = function () {
      const target = {};
      return new Proxy(target, {
        get(t, p) { if (p in t) return t[p]; return (...args) => undefined; },
        set(t, p, v) { t[p] = v; return true; },
      });
    };
    window.IntersectionObserver = class {
      constructor(cb) { this.cb = cb; }
      observe() {} unobserve() {} disconnect() {}
    };
    window.Element.prototype.scrollIntoView = function () {};
    window.Element.prototype.setPointerCapture = function () {};
    // jsdom ships no matchMedia; every real browser has one.
    if (!window.matchMedia) {
      window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
    }
  },
});

const { window } = dom;
const doc = window.document;
const $ = (id) => doc.getElementById(id);
// top-level `const` values are lexical, not window props: read them via eval
const state = () => window.eval('state');

function assert(cond, label) {
  if (cond) notes.push('ok  ' + label);
  else problems.push('FAIL ' + label);
}

setTimeout(() => {
  try {
    assert(typeof window.calc === 'function', 'inline script executed (calc defined)');
    assert(state().total > 0, 'estimator state initialised: total=' + state().total);
    assert(doc.querySelectorAll('#faqList .faq-item').length === 7, 'FAQ rendered (7 items)');
    assert(doc.querySelectorAll('#testiTrack > div').length === 5, 'reviews rendered (5 slides)');
    assert(doc.querySelectorAll('#zoneGrid > div').length === 16, 'service towns grid rendered (16)');
    assert(doc.querySelectorAll('a[href="#"]').length === 0, 'no dead # links');
    assert(!/555\) 546/.test(doc.body.textContent), 'no placeholder phone in visible text');

    // ZIP checker
    $('zipInput').value = '36101';
    window.checkZip();
    assert(/ZONE A/.test($('zipResult').textContent), 'ZIP 36101 -> ZONE A (local)');
    $('zipInput').value = '90210';
    window.checkZip();
    assert(/ZONE C/.test($('zipResult').textContent), 'ZIP 90210 -> ZONE C (custom fleet)');

    // estimator
    const before = state().total;
    window.setService('industrial');
    assert(state().service === 'industrial' && state().total !== before, 'setService changes price (' + before + ' -> ' + state().total + ')');
    window.setSize(10000);
    assert(state().size === 10000, 'setSize updates state');
    window.toggleAddon('gutter');
    assert(state().addons.has('gutter'), 'addon toggles on');
    window.toggleAddon('gutter');
    assert(!state().addons.has('gutter'), 'addon toggles off');
    window.resetEstimator();
    assert(state().size === 5000 && state().total > 0, 'resetEstimator restores defaults ($' + state().total + ')');
    assert($('quoteTotal').textContent.length > 0, 'quote total rendered: ' + $('quoteTotal').textContent);

    // booking flow end to end
    window.openBooking();
    assert(!$('bookingModal').classList.contains('hidden'), 'modal opens');
    window.goStep(2);
    assert($('bStep2').classList.contains('hidden'), 'goStep(2) blocked while details empty');
    $('fName').value = 'Jane Doe';
    $('fPhone').value = '334-555-121';          // 9 digits -> must be rejected
    $('fAddr').value = '1 Main St, Montgomery, AL 36101';
    window.goStep(2);
    assert($('bStep2').classList.contains('hidden'), 'short phone rejected');
    $('fPhone').value = '(334) 555-0123';
    window.goStep(2);
    assert(!$('bStep2').classList.contains('hidden'), 'valid details advance to step 2');
    assert(doc.querySelectorAll('#dayGrid button').length === 14, '14 bookable days rendered');
    const dayBtn = doc.querySelectorAll('#dayGrid button')[2];
    dayBtn.click();
    assert(state().booking.day !== null, 'day selected: ' + state().booking.day.label);
    assert(doc.querySelectorAll('#slotGrid button').length === 5, '5 time slots rendered');
    assert(doc.querySelectorAll('#slotGrid button:disabled').length === 0, 'no slots falsely marked taken');
    doc.querySelectorAll('#slotGrid button')[1].click();
    assert(state().booking.slot !== null, 'slot selected: ' + state().booking.slot);
    window.goStep(3);
    assert(/ORDER REVIEW/.test($('confirmSummary').textContent), 'order review rendered');
    window.confirmBooking();
    assert($('bSuccess').classList.contains('hidden'), 'confirm blocked until agreement ticked');
    $('agreeBox').checked = true;
    window.confirmBooking();
    assert(!$('bSuccess').classList.contains('hidden'), 'success panel shows');
    assert(/^LEAF-\d{4}-\d{4}$/.test($('bookingId').textContent.trim()), 'booking ref issued: ' + $('bookingId').textContent.trim());
    const mail = $('sendEmail').getAttribute('href');
    const text = $('sendText').getAttribute('href');
    assert(mail.startsWith('mailto:Corinthianbrown@checkchasinempire.onmicrosoft.com?subject='), 'email handoff addressed');
    assert(decodeURIComponent(mail).includes('Jane Doe') && decodeURIComponent(mail).includes('$'), 'email body carries the lead details');
    assert(text.startsWith('sms:+13347773031'), 'text handoff addressed to dispatch');
    assert($('sendCall').getAttribute('href') === 'tel:+13347773031', 'call handoff addressed');
    window.copyBooking();
    window.closeBooking();
    assert($('bookingModal').classList.contains('hidden'), 'modal closes');

    // FAQ accordion + aria
    const faqBtns = doc.querySelectorAll('#faqList button');
    assert(faqBtns[0].getAttribute('aria-expanded') === 'true', 'first FAQ open by default');
    faqBtns[1].click();
    assert(faqBtns[1].getAttribute('aria-expanded') === 'true' && faqBtns[0].getAttribute('aria-expanded') === 'false', 'FAQ accordion toggles aria-expanded');

    // menu
    $('menuBtn').click();
    assert(!$('mobileMenu').classList.contains('hidden') && $('menuBtn').getAttribute('aria-expanded') === 'true', 'mobile menu opens with aria-expanded');
    $('menuBtn').click();
    assert($('mobileMenu').classList.contains('hidden'), 'mobile menu closes');

    // coupon -> sms deep link (jsdom reports navigation as unimplemented)
    $('couponPhone').value = '3345550123';
    window.claimCoupon();
    notes.push('ok  claimCoupon ran without throwing');
  } catch (err) {
    problems.push('EXCEPTION: ' + (err && err.stack ? err.stack.split('\n').slice(0, 4).join(' | ') : err));
  }

  console.log('--- smoke notes ---');
  notes.forEach((n) => console.log('  ' + n));
  console.log('--- problems: ' + problems.length + ' ---');
  problems.forEach((p) => console.log('  ' + p));
  process.exit(problems.length ? 1 : 0);
}, 600);
