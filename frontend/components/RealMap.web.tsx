import { View, StyleSheet, Text } from 'react-native';
import { useMemo } from 'react';
import React from 'react';

export type ZonePolygonProp = {
  coordinates: Array<{ latitude: number; longitude: number }>;
  color?: string;
  fillColor?: string;
  name?: string;
  risk_level?: string;
};

export type MapMarkerProp = {
  latitude: number;
  longitude: number;
  title: string;
  color?: string;
  icon?: string;
  subtitle?: string;
};

export type RealMapProps = {
  region: {
    latitude: number;
    longitude: number;
    latitudeDelta?: number;
    longitudeDelta?: number;
    zoom?: number;
  };
  markers?: MapMarkerProp[];
  route?: Array<{ latitude: number; longitude: number }>;
  polygon?: Array<{ latitude: number; longitude: number }>;
  polygons?: ZonePolygonProp[];
  overlayTitle?: string;
  overlayText?: string;
  height?: number | string;
};

function buildMapHtml({
  region,
  markers = [],
  route = [],
  polygon = [],
  polygons = [],
}: {
  region: RealMapProps['region'];
  markers?: MapMarkerProp[];
  route?: Array<{ latitude: number; longitude: number }>;
  polygon?: Array<{ latitude: number; longitude: number }>;
  polygons?: ZonePolygonProp[];
}) {
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
      coords: poly.coordinates.map((p: { latitude: number; longitude: number }) => [p.latitude, p.longitude]),
      color:
        poly.color ||
        (poly.risk_level === 'critical' || poly.risk_level === 'high'
          ? '#ef4444'
          : poly.risk_level === 'medium'
          ? '#f59e0b'
          : '#10b981'),
      fillColor:
        poly.fillColor ||
        (poly.risk_level === 'critical' || poly.risk_level === 'high'
          ? '#ef4444'
          : poly.risk_level === 'medium'
          ? '#f59e0b'
          : '#10b981'),
      name: poly.name || 'Safety Zone',
    }))
  );

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    html, body, #map { margin: 0; padding: 0; height: 100%; width: 100%; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; }
    .leaflet-popup-content-wrapper { background: #1e293b; color: #f8fafc; border-radius: 8px; border: 1px solid #334155; }
    .leaflet-popup-tip { background: #1e293b; }
    .leaflet-popup-content { font-size: 12px; font-weight: 500; margin: 8px 12px; line-height: 1.4; }
    .custom-div-icon { display: flex; align-items: center; justify-content: center; border-radius: 50%; border: 2px solid #ffffff; box-shadow: 0 2px 6px rgba(0,0,0,0.4); font-weight: bold; color: #fff; font-size: 11px; }
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    var map = L.map('map', { zoomControl: true }).setView([${region.latitude}, ${region.longitude}], ${region.zoom || 13});
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
      maxZoom: 19,
    }).addTo(map);

    var bounds = [];

    var route = ${routeJson};
    if (route.length > 1) {
      L.polyline(route, { color: '#38bdf8', weight: 4, opacity: 0.85, dashArray: '6, 8' }).addTo(map);
      bounds = bounds.concat(route);
    }

    var polygons = ${polygonsJson};
    polygons.forEach(function(poly) {
      if (poly.coords && poly.coords.length > 2) {
        var p = L.polygon(poly.coords, {
          color: poly.color,
          weight: 2,
          fillColor: poly.fillColor,
          fillOpacity: 0.25
        }).addTo(map);
        if (poly.name) {
          p.bindPopup(poly.name);
        }
        bounds = bounds.concat(poly.coords);
      }
    });

    var markers = ${markersJson};
    markers.forEach(function (m) {
      var color = m.color || '#3b82f6';
      var customIcon = L.divIcon({
        className: 'custom-div-icon',
        html: '<div style="background-color:' + color + ';width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:10px;font-weight:bold;border:2px solid #fff;box-shadow:0 2px 5px rgba(0,0,0,0.4);">' + (m.icon || '') + '</div>',
        iconSize: [24, 24],
        iconAnchor: [12, 12]
      });

      var marker = L.marker([m.latitude, m.longitude], { icon: customIcon, title: m.title }).addTo(map);
      var popupContent = '<strong>' + m.title + '</strong>' + (m.subtitle ? '<br/><span style="color:#94a3b8;font-size:11px;">' + m.subtitle + '</span>' : '');
      marker.bindPopup(popupContent);
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
  height = 360,
}: RealMapProps) {
  const html = useMemo(
    () => buildMapHtml({ region, markers, route, polygon, polygons }),
    [region, markers, route, polygon, polygons]
  );

  return (
    <View style={styles.wrapper}>
      <View style={[styles.frame, { minHeight: typeof height === 'number' ? height : 360 }]}>
        {React.createElement('iframe', {
          title: 'TourSafe map',
          srcDoc: html,
          loading: 'lazy',
          style: { width: '100%', height: height, border: 0 },
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
    borderRadius: 14,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#334155',
  },
  frame: {
    borderRadius: 14,
    overflow: 'hidden',
    backgroundColor: '#0f172a',
  },
  overlay: {
    marginTop: 10,
    borderRadius: 10,
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
    padding: 12,
  },
  overlayTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#f8fafc',
  },
  overlayText: {
    marginTop: 4,
    fontSize: 12,
    color: '#94a3b8',
    lineHeight: 18,
  },
});
