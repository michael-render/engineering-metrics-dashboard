import type { MetricsReport } from '../types/index.js';
import { formatReportAsSlack } from './generator.js';

export async function sendSlackNotification(
  report: MetricsReport,
  webhookUrl: string
): Promise<void> {
  const payload = formatReportAsSlack(report);

  const response = await fetch(webhookUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Slack notification failed: ${response.status} ${response.statusText}`);
  }

  console.log('Slack notification sent successfully');
}

export async function sendNotifications(
  report: MetricsReport,
  config: { slackWebhookUrl?: string }
): Promise<void> {
  const notifications: Promise<void>[] = [];

  if (config.slackWebhookUrl) {
    notifications.push(
      sendSlackNotification(report, config.slackWebhookUrl).catch(error => {
        console.error('Failed to send Slack notification:', error);
      })
    );
  }

  await Promise.all(notifications);
}
