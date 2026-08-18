import crypto from 'node:crypto'
import { test, expect } from '../../../core/fixtures'
import { ADMIN_EMAIL, ADMIN_PASSWORD, makeStudent } from '../../../core/instance'
import { createStudent, getOrg, login, req } from '../../../core/client'

test.describe('payments/bold sandbox', () => {
  test('checkout + webhook activates enrollment', async () => {
    test.skip(process.env.E2E_BOLD_ENABLED !== '1', 'Set E2E_BOLD_ENABLED=1 to run Bold sandbox flow')

    const webhookSecret = process.env.E2E_BOLD_WEBHOOK_SECRET
    test.skip(!webhookSecret, 'Set E2E_BOLD_WEBHOOK_SECRET to validate webhook signature flow')

    const adminToken = await login(ADMIN_EMAIL, ADMIN_PASSWORD)
    const org = await getOrg()

    const config = await req<any>(
      'POST',
      `/payments/${org.id}/config?provider=BOLD&enabled=true`,
      adminToken,
      { provider: 'BOLD', enabled: true },
    )

    const offer = await req<any>(
      'POST',
      `/payments/${org.id}/offers`,
      adminToken,
      {
        name: `Bold Sandbox ${Date.now()}`,
        description: 'E2E Bold sandbox checkout',
        offer_type: 'one_time',
        price_type: 'fixed_price',
        amount: 19,
        currency: 'COP',
        is_publicly_listed: false,
      },
    )

    expect(offer.payments_config_id).toBe(config.id)

    const student = makeStudent('bold')
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
    const enrollment = pendingEnrollments[0]
    expect(enrollment.status).toBe('pending')

    // Mirrors Bold's CloudEvents webhook envelope — see
    // https://developers.bold.co/webhook. The merchant reference we set at
    // checkout time comes back at data.metadata.reference.
    const payload = {
      id: `evt_${Date.now()}`,
      type: 'SALE_APPROVED',
      data: {
        metadata: { reference: String(enrollment.id) },
      },
    }
    const rawBody = JSON.stringify(payload)
    // Bold signs the base64-encoded body, not the raw bytes, hex-encoded.
    const signature = crypto
      .createHmac('sha256', webhookSecret as string)
      .update(Buffer.from(rawBody).toString('base64'))
      .digest('hex')

    const webhookResult = await req<any>(
      'POST',
      '/payments/webhooks/bold',
      null,
      payload,
      false,
      { 'x-bold-signature': signature },
    )

    expect(webhookResult.ok).toBe(true)

    const activeEnrollments = await req<any[]>(
      'GET',
      `/payments/${org.id}/enrollments/mine`,
      studentToken,
    )
    expect(activeEnrollments[0].status).toBe('active')

    // Ensure duplicate webhook is idempotent.
    const duplicateResponse = await fetch(`${process.env.E2E_API_URL || 'http://localhost:8080/api/v1'}/payments/webhooks/bold`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-bold-signature': signature,
      },
      body: rawBody,
    })
    expect(duplicateResponse.ok).toBeTruthy()
  })
})
