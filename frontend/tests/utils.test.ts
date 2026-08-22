/**
 * TourSafe Frontend Utility Functions Test Suite
 * Tests haversine distance, coordinate formatting, color mappings, and status badges.
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  haversineDistance,
  formatCoords,
  kmToMeters,
  severityBadgeColor,
  zoneTypeColor,
  incidentStatusColor,
  getStatusDot,
} from "../lib/utils";

describe("1. Geospatial Haversine & Coordinate Math", () => {
  it("should calculate zero distance for identical coordinates", () => {
    const dist = haversineDistance(10.2381, 77.4892, 10.2381, 77.4892);
    assert.equal(dist, 0);
  });

  it("should calculate accurate great-circle distance between two known points", () => {
    // Distance between Kodaikanal Lake (10.2381, 77.4892) and Pillar Rocks (10.2185, 77.4674)
    // Approx ~3.16 km
    const dist = haversineDistance(10.2381, 77.4892, 10.2185, 77.4674);
    assert.ok(dist > 3.0 && dist < 3.3, `Distance should be ~3.16km, got ${dist}`);
  });

  it("should convert km to meters accurately", () => {
    assert.equal(kmToMeters(1.5), 1500);
    assert.equal(kmToMeters(0), 0);
    assert.equal(kmToMeters(10.25), 10250);
  });

  it("should format coordinates with cardinal directions correctly", () => {
    const formatted1 = formatCoords(10.23811, 77.48918);
    assert.equal(formatted1, "10.23811° N, 77.48918° E");

    const formatted2 = formatCoords(-33.8688, -151.2093);
    assert.equal(formatted2, "33.86880° S, 151.20930° W");
  });
});

describe("2. Color Tokens & Semantic Status Badges", () => {
  it("should return official high-visibility colors for alert severities", () => {
    assert.ok(severityBadgeColor("critical").includes("bg-ts-alert-red"));
    assert.ok(severityBadgeColor("high").includes("bg-ts-saffron"));
    assert.ok(severityBadgeColor("medium").includes("bg-yellow-500"));
    assert.ok(severityBadgeColor("low").includes("bg-ts-teal"));
  });

  it("should return standardized hex color codes for safety zone types", () => {
    assert.equal(zoneTypeColor("safe"), "#046A38");
    assert.equal(zoneTypeColor("warning"), "#D97706");
    assert.equal(zoneTypeColor("danger"), "#C53030");
    assert.equal(zoneTypeColor("restricted"), "#4A5568");
  });

  it("should return correct status classes for incident lifecycles", () => {
    assert.ok(incidentStatusColor("reported").includes("text-ts-saffron"));
    assert.ok(incidentStatusColor("dispatched").includes("text-blue-700"));
    assert.ok(incidentStatusColor("resolved").includes("text-ts-green"));
    assert.ok(incidentStatusColor("closed").includes("text-ts-slate"));
  });

  it("should return correct dot background classes for safety dot indicator", () => {
    assert.equal(getStatusDot("safe"), "bg-ts-green");
    assert.equal(getStatusDot("alert"), "bg-ts-saffron");
    assert.equal(getStatusDot("sos"), "bg-ts-alert-red");
    assert.equal(getStatusDot("inactive"), "bg-gray-400");
  });
});
