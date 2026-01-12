import { format } from 'date-fns';
import type { DoraMetrics, MetricsReport, MetricsTrends, MetricsPeriod } from '../types/index.js';
import { getOverallRating, formatRating } from '../metrics/dora.js';

export interface ReportGeneratorInput {
  currentMetrics: DoraMetrics;
  previousMetrics?: DoraMetrics;
}

export function generateReport(input: ReportGeneratorInput): MetricsReport {
  const { currentMetrics, previousMetrics } = input;

  const trends = calculateTrends(currentMetrics, previousMetrics);
  const highlights = generateHighlights(currentMetrics, trends);
  const recommendations = generateRecommendations(currentMetrics);

  const periodLabel = currentMetrics.period.type === 'weekly' ? 'Weekly' : 'Monthly';
  const dateRange = `${format(currentMetrics.period.startDate, 'MMM d')} - ${format(currentMetrics.period.endDate, 'MMM d, yyyy')}`;

  return {
    title: `${periodLabel} Engineering Metrics Report: ${dateRange}`,
    period: currentMetrics.period,
    metrics: currentMetrics,
    trends,
    highlights,
    recommendations,
    generatedAt: new Date(),
  };
}

function calculateTrends(
  current: DoraMetrics,
  previous?: DoraMetrics
): MetricsTrends {
  if (!previous) {
    return {
      deploymentFrequencyChange: 0,
      leadTimeChange: 0,
      changeFailureRateChange: 0,
      mttrChange: 0,
    };
  }

  const calculateChange = (curr: number, prev: number): number => {
    if (prev === 0) return curr > 0 ? 100 : 0;
    return ((curr - prev) / prev) * 100;
  };

  return {
    deploymentFrequencyChange: calculateChange(
      current.deploymentFrequency.deploymentsPerDay,
      previous.deploymentFrequency.deploymentsPerDay
    ),
    leadTimeChange: calculateChange(
      current.leadTime.medianHours,
      previous.leadTime.medianHours
    ),
    changeFailureRateChange: calculateChange(
      current.changeFailureRate.percentage,
      previous.changeFailureRate.percentage
    ),
    mttrChange: calculateChange(
      current.mttr.medianHours,
      previous.mttr.medianHours
    ),
  };
}

function generateHighlights(
  metrics: DoraMetrics,
  trends: MetricsTrends
): string[] {
  const highlights: string[] = [];
  const overallRating = getOverallRating(metrics);

  highlights.push(`Overall DORA rating: ${formatRating(overallRating)}`);

  if (metrics.deploymentFrequency.rating === 'elite') {
    highlights.push(
      `Deploying ${metrics.deploymentFrequency.deploymentsPerDay.toFixed(1)}x per day - Elite level!`
    );
  }

  if (trends.deploymentFrequencyChange > 20) {
    highlights.push(
      `Deployment frequency increased ${trends.deploymentFrequencyChange.toFixed(0)}% from last period`
    );
  }

  if (metrics.leadTime.rating === 'elite' || metrics.leadTime.rating === 'high') {
    highlights.push(
      `Lead time of ${metrics.leadTime.medianHours.toFixed(1)} hours is ${formatRating(metrics.leadTime.rating)}`
    );
  }

  if (trends.leadTimeChange < -20) {
    highlights.push(
      `Lead time improved by ${Math.abs(trends.leadTimeChange).toFixed(0)}%`
    );
  }

  if (metrics.changeFailureRate.percentage < 5) {
    highlights.push(
      `Change failure rate of ${metrics.changeFailureRate.percentage.toFixed(1)}% is excellent`
    );
  }

  if (metrics.mttr.incidents === 0) {
    highlights.push('Zero incidents this period!');
  } else if (metrics.mttr.rating === 'elite' || metrics.mttr.rating === 'high') {
    highlights.push(
      `MTTR of ${metrics.mttr.medianHours.toFixed(1)} hours demonstrates strong incident response`
    );
  }

  return highlights.slice(0, 5);
}

function generateRecommendations(metrics: DoraMetrics): string[] {
  const recommendations: string[] = [];

  if (metrics.deploymentFrequency.rating === 'low' || metrics.deploymentFrequency.rating === 'medium') {
    recommendations.push(
      'Consider implementing continuous deployment to increase deployment frequency'
    );
    recommendations.push(
      'Break down large changes into smaller, more frequent deployments'
    );
  }

  if (metrics.leadTime.rating === 'low' || metrics.leadTime.rating === 'medium') {
    recommendations.push(
      'Review PR review process - consider async reviews or pair programming'
    );
    recommendations.push(
      'Implement automated testing to speed up the review cycle'
    );
  }

  if (metrics.changeFailureRate.rating === 'low' || metrics.changeFailureRate.rating === 'medium') {
    recommendations.push(
      'Enhance automated testing coverage, especially integration tests'
    );
    recommendations.push(
      'Consider implementing feature flags for safer rollouts'
    );
    recommendations.push(
      'Review deployment process for potential failure points'
    );
  }

  if (metrics.mttr.rating === 'low' || metrics.mttr.rating === 'medium') {
    recommendations.push(
      'Improve observability with better logging and monitoring'
    );
    recommendations.push(
      'Create runbooks for common incident scenarios'
    );
    recommendations.push(
      'Practice incident response with game days'
    );
  }

  return recommendations.slice(0, 5);
}

export function formatReportAsMarkdown(report: MetricsReport): string {
  const { metrics, trends, highlights, recommendations } = report;
  const overallRating = getOverallRating(metrics);

  const trendArrow = (change: number, inverse = false): string => {
    const improved = inverse ? change < 0 : change > 0;
    if (Math.abs(change) < 5) return '→';
    return improved ? '↑' : '↓';
  };

  const formatPercent = (value: number): string => {
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toFixed(1)}%`;
  };

  return `# ${report.title}

## Overall Performance: ${formatRating(overallRating)}

Generated: ${format(report.generatedAt, 'MMMM d, yyyy h:mm a')}

---

## DORA Metrics Summary

| Metric | Value | Rating | Trend |
|--------|-------|--------|-------|
| Deployment Frequency | ${metrics.deploymentFrequency.deploymentsPerDay.toFixed(2)}/day | ${formatRating(metrics.deploymentFrequency.rating)} | ${trendArrow(trends.deploymentFrequencyChange)} ${formatPercent(trends.deploymentFrequencyChange)} |
| Lead Time for Changes | ${metrics.leadTime.medianHours.toFixed(1)} hours | ${formatRating(metrics.leadTime.rating)} | ${trendArrow(trends.leadTimeChange, true)} ${formatPercent(trends.leadTimeChange)} |
| Change Failure Rate | ${metrics.changeFailureRate.percentage.toFixed(1)}% | ${formatRating(metrics.changeFailureRate.rating)} | ${trendArrow(trends.changeFailureRateChange, true)} ${formatPercent(trends.changeFailureRateChange)} |
| Mean Time to Recovery | ${metrics.mttr.medianHours.toFixed(1)} hours | ${formatRating(metrics.mttr.rating)} | ${trendArrow(trends.mttrChange, true)} ${formatPercent(trends.mttrChange)} |

---

## Key Highlights

${highlights.map(h => `- ${h}`).join('\n')}

---

## Detailed Metrics

### Deployment Frequency
- **Total Deployments:** ${metrics.deploymentFrequency.totalDeployments}
- **Per Day:** ${metrics.deploymentFrequency.deploymentsPerDay.toFixed(2)}
- **Per Week:** ${metrics.deploymentFrequency.deploymentsPerWeek.toFixed(1)}

### Lead Time for Changes
- **Median:** ${metrics.leadTime.medianHours.toFixed(1)} hours
- **Average:** ${metrics.leadTime.averageHours.toFixed(1)} hours
- **P90:** ${metrics.leadTime.p90Hours.toFixed(1)} hours

### Change Failure Rate
- **Failure Rate:** ${metrics.changeFailureRate.percentage.toFixed(1)}%
- **Failed Changes:** ${metrics.changeFailureRate.failedDeployments}
- **Total Changes:** ${metrics.changeFailureRate.totalDeployments}

### Mean Time to Recovery
- **Median MTTR:** ${metrics.mttr.medianHours.toFixed(1)} hours
- **Average MTTR:** ${metrics.mttr.averageHours.toFixed(1)} hours
- **Incidents:** ${metrics.mttr.incidents}

---

## Recommendations

${recommendations.map((r, i) => `${i + 1}. ${r}`).join('\n')}

---

*Report generated by Engineering Metrics Dashboard*
`;
}

export function formatReportAsSlack(report: MetricsReport): object {
  const { metrics, trends, highlights } = report;
  const overallRating = getOverallRating(metrics);

  const ratingEmoji: Record<string, string> = {
    elite: ':star2:',
    high: ':white_check_mark:',
    medium: ':warning:',
    low: ':red_circle:',
  };

  return {
    blocks: [
      {
        type: 'header',
        text: {
          type: 'plain_text',
          text: report.title,
        },
      },
      {
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `*Overall Rating:* ${ratingEmoji[overallRating]} ${formatRating(overallRating)}`,
        },
      },
      {
        type: 'divider',
      },
      {
        type: 'section',
        fields: [
          {
            type: 'mrkdwn',
            text: `*Deployment Frequency*\n${metrics.deploymentFrequency.deploymentsPerDay.toFixed(2)}/day ${ratingEmoji[metrics.deploymentFrequency.rating]}`,
          },
          {
            type: 'mrkdwn',
            text: `*Lead Time*\n${metrics.leadTime.medianHours.toFixed(1)} hours ${ratingEmoji[metrics.leadTime.rating]}`,
          },
          {
            type: 'mrkdwn',
            text: `*Change Failure Rate*\n${metrics.changeFailureRate.percentage.toFixed(1)}% ${ratingEmoji[metrics.changeFailureRate.rating]}`,
          },
          {
            type: 'mrkdwn',
            text: `*MTTR*\n${metrics.mttr.medianHours.toFixed(1)} hours ${ratingEmoji[metrics.mttr.rating]}`,
          },
        ],
      },
      {
        type: 'divider',
      },
      {
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `*Key Highlights*\n${highlights.map(h => `• ${h}`).join('\n')}`,
        },
      },
    ],
  };
}
