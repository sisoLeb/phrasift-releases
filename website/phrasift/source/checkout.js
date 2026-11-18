'use strict';

const element = id => document.getElementById(id);
const page = element('checkout');
const frame = element('payment-frame');
const status = element('checkout-status');
const retry = element('retry');
const params = new URLSearchParams(location.search);
const isTest = page.dataset.mode === 'test';
const hasTransaction = params.has('_ptxn');
const plans = {
  standard: { name: 'Phrasift Standard', price: '€49.99', id: page.dataset.standard },
  pro: { name: 'Phrasift Pro', price: '€99.99', id: page.dataset.pro },
};
const edition = params.get('edition');
const selected = !hasTransaction && Object.hasOwn(plans, edition) ? edition : null;
const plan = selected ? plans[selected] : null;
let loadTimer;
let completed = false;

function describeOrder(key) {
  element('checkout-title').textContent = plans[key].name;
  element('order-detail').textContent = 'One-time license for Windows and Mac.';
  element('features').hidden = false;
  element('pro-feature').hidden = key !== 'pro';
  element(`edition-${key}`).setAttribute('aria-current', 'page');
}

function report(message, canRetry = false) {
  status.textContent = message;
  status.hidden = !message;
  retry.hidden = !canRetry;
}

function showOrder(data) {
  const items = data?.items;
  const totals = data?.totals;
  if (!Array.isArray(items) || items.length !== 1 || items[0].quantity !== 1 || items[0].billing_cycle) return false;
  const actual = Object.keys(plans).find(key => plans[key].id === items[0].price_id);
  if (!actual || (selected && actual !== selected)) return false;
  if (!/^[A-Z]{3}$/.test(data.currency_code) || !Number.isFinite(totals?.subtotal)
      || !Number.isFinite(totals.tax) || !Number.isFinite(totals.total)) return false;

  describeOrder(actual);
  const money = new Intl.NumberFormat(undefined, { style: 'currency', currency: data.currency_code });
  for (const key of ['subtotal', 'discount', 'tax', 'credit']) {
    const amount = totals[key];
    const optional = key === 'discount' || key === 'credit';
    element(`${key}-row`).hidden = optional && !amount;
    if (Number.isFinite(amount)) element(key).textContent = money.format(optional ? -Math.abs(amount) : amount);
  }
  element('total-label').textContent = 'Total due';
  element('total').textContent = money.format(totals.balance ?? totals.total);
  element('totals').hidden = false;
  return true;
}

function checkoutEvent(event) {
  if (completed) return;
  if (['checkout.loaded', 'checkout.updated', 'checkout.discount.applied', 'checkout.discount.removed',
    'checkout.customer.updated', 'checkout.items.updated', 'checkout.items.removed'].includes(event.name)) {
    if (!event.data?.items && event.name !== 'checkout.loaded') return;
    clearTimeout(loadTimer);
    frame.hidden = !showOrder(event.data);
    report(frame.hidden ? 'We could not verify this order. Return to plans and open a new checkout.' : '');
  } else if (event.name === 'checkout.completed') {
    clearTimeout(loadTimer);
    completed = true;
    frame.hidden = true;
    element('payment-title').textContent = isTest ? 'Test payment complete' : 'Payment complete';
    element('editions').hidden = true;
    element('delivery').hidden = true;
    report(isTest ? 'Paddle completed this test order. No money was charged.' :
      'Check your inbox for your Phrasift license key and installer link. If the email doesn’t arrive, check spam or contact support with your Paddle receipt.');
  } else if (event.name === 'checkout.error' || event.name === 'checkout.closed') {
    clearTimeout(loadTimer);
    frame.hidden = true;
    report('Checkout could not open. Reload to try again or contact support.', true);
  }
}

function startCheckout() {
  if (!plan && !hasTransaction) return;
  frame.hidden = true;
  if (!new RegExp(`^${isTest ? 'test' : 'live'}_[a-zA-Z0-9]+$`).test(page.dataset.token) || !window.Paddle) {
    report('The payment form is unavailable. Reload to try again or contact support.', true);
    return;
  }
  report('Loading the payment form…');
  loadTimer = setTimeout(() => report('The payment form is taking longer than expected.', true), 12000);
  try {
    if (isTest) Paddle.Environment.set('sandbox');
    Paddle.Initialize({
      token: page.dataset.token,
      checkout: { settings: {
        displayMode: 'inline', theme: 'light', variant: 'one-page',
        frameTarget: 'payment-frame', frameInitialHeight: 450,
        frameStyle: 'width: 100%; min-width: 286px; background-color: transparent; border: none;',
      } },
      eventCallback: checkoutEvent,
    });
    // Paddle opens transaction links automatically from the _ptxn parameter.
    if (plan) Paddle.Checkout.open({ items: [{ priceId: plan.id, quantity: 1 }] });
  } catch {
    checkoutEvent({ name: 'checkout.error' });
  }
}

element('test-note').hidden = !isTest;
element('editions').hidden = hasTransaction;
if (hasTransaction) element('checkout-title').textContent = 'Your Phrasift order';
if (plan) {
  describeOrder(selected);
  element('total').textContent = plan.price;
  element('totals').hidden = false;
}
startCheckout();
