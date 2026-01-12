// Engineering Metrics Dashboard
// Main entry point for the metrics calculation library

export * from './types/index.js';
export * from './clients/index.js';
export * from './metrics/index.js';
export * from './reports/index.js';

// Re-export commonly used functions
export { calculateDoraMetrics, getOverallRating, formatRating } from './metrics/dora.js';
export { generateReport, formatReportAsMarkdown, formatReportAsSlack } from './reports/generator.js';
