import { View, StyleSheet, Text } from 'react-native';
import { useMemo } from 'react';
import React from 'react';

type LatLng = { latitude: number; longitude: number };

export type ZonePolygonProp = {
  coordinates: LatLng[];
  color?: string;
  fillColor?: string;
  name?: string;
  risk_level?: string;
};

type RealMapProps = {
  region: {
    latitude: number;
    longitude: number;
    latitudeDelta?: number;
    longitudeDelta?: number;
    zoom?: number;
  };
  markers?: Array<{
    latitude: number;
    longitude: number;
    title: string;
    color?: string;
  }>;
  route?: LatLng[];
  polygon?: LatLng[];
  polygons?: ZonePolygonProp[];
  overlayTitle?: string;
  overlayText?: string;
};

// Leaflet loaded from CDN inside the iframe's own document
function buildMapHtml({
  region,
  markers = [],
  route = [],
  polygon = [],
  polygons = [],
}: {
  region: RealMapProps['region'];
  markers?: RealMapProps['markers'];
  route?: LatLng[];
  polygon?: LatLng[];
  polygons?: ZonePolygonProp[];
}) {
  // Combine single polygon into polygons array
  const allPolygons: ZonePolygonProp[] = [...polygons];
  if (polygon && polygon.length > 2) {
    allPolygons.push({
      coordinates: polygon,
      color: '#1e40af',
      fillColor: '#1e40af',
      name: 'Primary Boundary',
    });
  }

  const markersJson = JSON.stringify(markers || []);
  const routeJson = JSON.stringify((route || []).map((p) => [p.latitude, p.longitude]));
  const polygonsJson = JSON.stringify(
    allPolygons.map((poly) => ({
      coords: poly.coordinates.map((p) => [p.latitude, p.longitude]),
      color: poly.color || (poly.risk_level === 'critical' || poly.risk_level === 'high' ? '#ef4444' : poly.risk_level === 'medium' ? '#f59e0b' : '#10b981'),
      fillColor: poly.fillColor || (poly.risk_level === 'critical' || poly.risk_level === 'high' ? '#ef4444' : poly.risk_level === 'medium' ? '#f59e0b' : '#10b981'),
      name: poly.name || 'Safety Zone',
    }))
  );

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    html, body, #map { margin: 0; padding: 0; height: 100%; width: 100%; font-family: system-ui, sans-serif; }
    .leaflet-popup-content { font-size: 13px; font-weight: 600; }
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    var map = L.map('map', { zoomControl: true }).setView([${region.latitude}, ${region.longitude}], ${region.zoom || 13});
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    var bounds = [];

    var route = ${routeJson};
    if (route.length > 1) {
      L.polyline(route, { color: '#1e40af', weight: 4, opacity: 0.8 }).addTo(map);
      bounds = bounds.concat(route);
    }

    var polygons = ${polygonsJson};
    polygons.forEach(function(poly) {
      if (poly.coords && poly.coords.length > 2) {
        var p = L.polygon(poly.coords, {
          color: poly.color,
          weight: 2,
          fillColor: poly.fillColor,
          fillOpacity: 0.22
        }).addTo(map);
        if (poly.name) {
          p.bindPopup(poly.name);
        }
        bounds = bounds.concat(poly.coords);
      }
    });

    var markers = ${markersJson};
    markers.forEach(function (m) {
      L.marker([m.latitude, m.longitude], { title: m.title }).addTo(map).bindPopup(m.title);
      bounds.push([m.latitude, m.longitude]);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [36, 36], maxZoom: 15 });
    }
  </script>
</body>
</html>`;
}

export default function RealMap({
  region,
  markers = [],
  route = [],
  polygon = [],
  polygons = [],
  overlayTitle,
  overlayText,
}: RealMapProps) {
  const html = useMemo(
    () => buildMapHtml({ region, markers, route, polygon, polygons }),
    [region, markers, route, polygon, polygons]
  );

  return (
    <View style={styles.wrapper}>
      <View style={styles.frame}>
        {React.createElement('iframe', {
          title: 'TourSafe map',
          srcDoc: html,
          loading: 'lazy',
          style: { width: '100%', height: 320, border: 0 },
        })}
      </View>

      {(overlayTitle || overlayText) && (
        <View style={styles.overlay}>
          {overlayTitle ? <Text style={styles.overlayTitle}>{overlayTitle}</Text> : null}
          {overlayText ? <Text style={styles.overlayText}>{overlayText}</Text> : null}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    borderRadius: 16,
    overflow: 'hidden',
  },
  frame: {
    minHeight: 320,
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: '#dbeafe',
  },
  overlay: {
    marginTop: 12,
    borderRadius: 14,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#dbe3ef',
    padding: 12,
  },
  overlayTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#1a365d',
  },
  overlayText: {
    marginTop: 6,
    color: 'rgba(26,54,93,0.65)',
    fontSize: 12,
    lineHeight: 18,
  },
});
