import { test, expect } from '../../../core/fixtures'
import { ADMIN_EMAIL, ADMIN_PASSWORD, makeStudent } from '../../../core/instance'
import { createStudent, getOrg, login, req } from '../../../core/client'

test.describe('payments/openpay sandbox', () => {
  test('checkout creates a pending enrollment', async () => {
    test.skip(process.env.E2E_OPENPAY_ENABLED !== '1', 'Set E2E_OPENPAY_ENABLED=1 to run OpenPay sandbox flow')

    const adminToken = await login(ADMIN_EMAIL, ADMIN_PASSWORD)
    const org = await getOrg()

    const config = await req<any>(
      'POST',
      `/payments/${org.id}/config?provider=OPENPAY&enabled=true`,
      adminToken,
      { provider: 'OPENPAY', enabled: true },
    )

    const offer = await req<any>(
      'POST',
      `/payments/${org.id}/offers`,
      adminToken,
      {
        name: `OpenPay Sandbox ${Date.now()}`,
        description: 'E2E OpenPay sandbox checkout',
        offer_type: 'one_time',
        price_type: 'fixed_price',
        amount: 19000,
        currency: 'COP',
        is_publicly_listed: false,
      },
    )

    expect(offer.payments_config_id).toBe(config.id)

    const student = makeStudent('openpay')
    await createStudent(adminToken, org.id, {
      email: student.email,
      username: student.username,
      password: student.password,
      first_name: student.firstName,
      last_name: student.lastName,
    })
    const studentToken = await login(student.email, student.password)

    const checkout = await req<any>(
      'POST',
      `/payments/${org.id}/offers/${offer.offer_uuid}/checkout?redirect_uri=${encodeURIComponent('https://example.com/return')}`,
      studentToken,
    )

    expect(typeof checkout.checkout_url).toBe('string')
    expect(checkout.checkout_url.length).toBeGreaterThan(10)

    const pendingEnrollments = await req<any[]>(
      'GET',
      `/payments/${org.id}/enrollments/mine`,
      studentToken,
    )
    expect(pendingEnrollments.length).toBeGreaterThan(0)
    expect(pendingEnrollments[0].status).toBe('pending')

    // OpenPay Colombia doesn't sign webhook payloads, so verify_and_parse_webhook
    // confirms the transaction by calling back to OpenPay's own REST API rather
    // than trusting the POST body — a fake payload here can't drive activation
    // the way the Bold test does. Exercising the full activate path needs a real
    // sandbox charge completed through OpenPay's hosted card form, which belongs
    // in the end-to-end sandbox-credentials pass, not this synthetic test.
  })

  test('webhook acknowledges the registration handshake', async () => {
    test.skip(process.env.E2E_OPENPAY_ENABLED !== '1', 'Set E2E_OPENPAY_ENABLED=1 to run OpenPay sandbox flow')

    // Sent once by OpenPay when a webhook URL is registered; has no
    // transaction attached, so the handler must 200 it without a lookup.
    const result = await req<any>('POST', '/payments/webhooks/openpay', null, {
      type: 'verification',
      event_date: new Date().toISOString(),
      verification_code: 'e2e-test-code',
    })

    expect(result.ok).toBe(true)
    expect(result.status).toBe('ignored')
  })
})
