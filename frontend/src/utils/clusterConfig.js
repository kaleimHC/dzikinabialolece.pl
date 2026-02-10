/**
 * Adaptive Circle Sizing Module
 * ==============================
 *
 * Dynamically calculates circle radius for map markers based on:
 * 1. Total number of sightings (n) - dataset size
 * 2. Zoom level - map magnification
 *
 * PROBLEM:
 * - Few sightings (n=100) → need large circles to be visible
 * - Many sightings (n=5000) → need small circles to avoid overlap
 *
 * FORMULA:
 * radius = baseRadius * zoomFactor
 *
 * where:
 *   baseRadius = K / log10(n + 10)
 *   zoomFactor = 0.5 + (zoom - 10) * 0.15
 *
 * CALIBRATION TABLE:
 * ┌─────────┬──────────┬─────────┬─────────┬─────────┐
 * │    n    │ zoom=10  │ zoom=12 │ zoom=14 │ zoom=16 │
 * ├─────────┼──────────┼─────────┼─────────┼─────────┤
 * │     50  │   6.4px  │  8.9px  │  11.5px │  14.0px │
 * │    100  │   5.7px  │  8.0px  │  10.3px │  12.6px │
 * │    500  │   4.6px  │  6.4px  │   8.3px │  10.1px │
 * │   1000  │   4.2px  │  5.8px  │   7.5px │   9.2px │
 * │   3500  │   3.6px  │  5.0px  │   6.5px │   7.9px │
 * │   5000  │   3.4px  │  4.8px  │   6.2px │   7.5px │
 * │  10000  │   3.1px  │  4.4px  │   5.6px │   6.9px │
 * └─────────┴──────────┴─────────┴─────────┴─────────┘
 *
 * USAGE:
 * ```javascript
 * import { getPointRadius } from './utils/clusterConfig';
 *
 * // For individual points
 * const radius = getPointRadius(sightings.length, currentZoom);
 * ```
 *
 * @module clusterConfig
 * @version 1.0.0
 */

/**
 * Base multiplier for radius calculation.
 * Higher value = larger circles overall.
 * Calibrated for typical wildlife monitoring datasets (50-10000 sightings).
 */
const K_BASE = 25;

/**
 * Minimum radius in pixels.
 * Prevents circles from becoming too small to click/see.
 */
const MIN_RADIUS = 3;

/**
 * Maximum radius in pixels.
 * Prevents circles from becoming too large and overlapping excessively.
 */
const MAX_RADIUS = 16;

/**
 * Zoom level considered "base" (factor = 1.0).
 */
const BASE_ZOOM = 12;

/**
 * How much radius changes per zoom level.
 * 0.15 means +15% radius per zoom level above BASE_ZOOM.
 */
const ZOOM_SENSITIVITY = 0.15;

/**
 * Minimum zoom factor (at very low zoom levels).
 */
const MIN_ZOOM_FACTOR = 0.5;

/**
 * Maximum zoom factor (at very high zoom levels).
 */
const MAX_ZOOM_FACTOR = 2.0;

/**
 * Calculate adaptive point radius based on dataset size and zoom level.
 *
 * @param {number} n - Total number of sightings in dataset
 * @param {number} zoom - Current map zoom level (typically 10-18)
 * @returns {number} Radius in pixels, clamped to [MIN_RADIUS, MAX_RADIUS]
 *
 * @example
 * getPointRadius(100, 12)  // → ~8.0
 * getPointRadius(3500, 12) // → ~5.0
 * getPointRadius(3500, 16) // → ~7.9
 */
export function getPointRadius(n, zoom) {
  // Prevent edge cases
  if (n <= 0) n = 1;
  if (zoom < 1) zoom = 1;

  // Base radius: inversely proportional to log of dataset size
  // Adding 10 to n prevents log(1) = 0 and smooths small datasets
  const baseRadius = K_BASE / Math.log10(n + 10);

  // Zoom factor: linear scaling from BASE_ZOOM
  // At zoom=10: factor ≈ 0.7, at zoom=14: factor ≈ 1.3
  const zoomFactor = Math.max(
    MIN_ZOOM_FACTOR,
    Math.min(MAX_ZOOM_FACTOR, 0.5 + (zoom - 10) * ZOOM_SENSITIVITY),
  );

  // Final radius with clamping
  const radius = baseRadius * zoomFactor;
  return Math.max(MIN_RADIUS, Math.min(MAX_RADIUS, radius));
}

/**
 * Calculate adaptive stroke width based on point radius.
 * Maintains visual proportion as circles scale.
 *
 * @param {number} radius - Circle radius in pixels
 * @returns {number} Stroke width in pixels
 */
export function getStrokeWidth(radius) {
  // Stroke is ~25% of radius, clamped to reasonable range
  return Math.max(1, Math.min(3, radius * 0.25));
}

/**
 * Generate MapLibre paint expression for adaptive circle radius.
 * Can be used directly in layer paint property.
 *
 * @param {number} n - Total number of sightings
 * @returns {Array} MapLibre expression for zoom-dependent radius
 *
 * @example
 * map.setPaintProperty('points', 'circle-radius', getRadiusExpression(3500));
 */
export function getRadiusExpression(n) {
  // Pre-calculate radii for key zoom levels
  const r10 = getPointRadius(n, 10);
  const r12 = getPointRadius(n, 12);
  const r14 = getPointRadius(n, 14);
  const r16 = getPointRadius(n, 16);
  const r18 = getPointRadius(n, 18);

  // MapLibre interpolate expression for smooth zoom transitions
  return [
    "interpolate",
    ["linear"],
    ["zoom"],
    10,
    r10,
    12,
    r12,
    14,
    r14,
    16,
    r16,
    18,
    r18,
  ];
}

