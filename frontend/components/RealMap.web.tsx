import { View, StyleSheet, Text } from 'react-native';
import { useMemo } from 'react';
import React from 'react';

type LatLng = { latitude: number; longitude: number };

type RealMapProps = {
  region: {
    latitude: number;
    longitude: number;
    latitudeDelta: number;
    longitudeDelta: number;
  };
  markers?: Array<{
    latitude: number;
    longitude: number;
    title: string;
    color?: string;
  }>;
  route?: LatLng[];
  polygon?: LatLng[];
  overlayTitle?: string;
  overlayText?: string;
};

// Leaflet loaded from CDN inside the iframe's own document — keeps this a
// web-only concern with no react-native-maps/leaflet bundling dependency.
function buildMapHtml({
  region,
  markers,
  route,
  polygon,
}: Required<Pick<RealMapProps, 'region' | 'markers' | 'route' | 'polygon'>>) {
  const markersJson = JSON.stringify(markers);
  const routeJson = JSON.stringify(route.map((p) => [p.latitude, p.longitude]));
  const polygonJson = JSON.stringify(polygon.map((p) => [p.latitude, p.longitude]));

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    html, body, #map { margin: 0; padding: 0; height: 100%; width: 100%; }
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    var map = L.map('map', { zoomControl: true }).setView([${region.latitude}, ${region.longitude}], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    var bounds = [];

    var route = ${routeJson};
    if (route.length > 1) {
      var polyline = L.polyline(route, { color: '#1e40af', weight: 5 }).addTo(map);
      bounds = bounds.concat(route);
    }

    var polygonCoords = ${polygonJson};
    if (polygonCoords.length > 2) {
      L.polygon(polygonCoords, { color: '#1e40af', weight: 2, fillColor: '#1e40af', fillOpacity: 0.12 }).addTo(map);
      bounds = bounds.concat(polygonCoords);
    }

    var markers = ${markersJson};
    markers.forEach(function (m) {
      L.marker([m.latitude, m.longitude], { title: m.title }).addTo(map).bindPopup(m.title);
      bounds.push([m.latitude, m.longitude]);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [32, 32] });
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
  overlayTitle,
  overlayText,
}: RealMapProps) {
  const html = useMemo(
    () => buildMapHtml({ region, markers, route, polygon }),
    [region, markers, route, polygon]
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
