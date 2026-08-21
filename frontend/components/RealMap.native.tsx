import { View, StyleSheet, Text } from 'react-native';
import MapView, { Marker, Polygon, Polyline, PROVIDER_DEFAULT } from 'react-native-maps';

export type ZonePolygonProp = {
  coordinates: Array<{ latitude: number; longitude: number }>;
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
  route?: Array<{ latitude: number; longitude: number }>;
  polygon?: Array<{ latitude: number; longitude: number }>;
  polygons?: ZonePolygonProp[];
  overlayTitle?: string;
  overlayText?: string;
};

export default function RealMap({
  region,
  markers = [],
  route = [],
  polygon = [],
  polygons = [],
  overlayTitle,
  overlayText,
}: RealMapProps) {
  const allPolygons: ZonePolygonProp[] = [...polygons];
  if (polygon && polygon.length > 2) {
    allPolygons.push({
      coordinates: polygon,
      color: '#1e40af',
      fillColor: 'rgba(30,64,175,0.12)',
      name: 'Primary Boundary',
    });
  }

  return (
    <View style={styles.wrapper}>
      <MapView
        style={styles.map}
        provider={PROVIDER_DEFAULT}
        initialRegion={{
          latitude: region.latitude,
          longitude: region.longitude,
          latitudeDelta: region.latitudeDelta || 0.08,
          longitudeDelta: region.longitudeDelta || 0.08,
        }}
        showsCompass
        showsScale
        showsMyLocationButton={false}
        toolbarEnabled={false}
      >
        {route.length > 1 && <Polyline coordinates={route} strokeWidth={4} strokeColor="#1e40af" />}
        {allPolygons.map((poly, idx) => {
          const strokeColor =
            poly.color ||
            (poly.risk_level === 'critical' || poly.risk_level === 'high'
              ? '#ef4444'
              : poly.risk_level === 'medium'
              ? '#f59e0b'
              : '#10b981');
          const fillColor =
            poly.fillColor ||
            (poly.risk_level === 'critical' || poly.risk_level === 'high'
              ? 'rgba(239, 68, 68, 0.2)'
              : poly.risk_level === 'medium'
              ? 'rgba(245, 158, 11, 0.2)'
              : 'rgba(16, 185, 129, 0.2)');

          return (
            <Polygon
              key={`poly-${idx}-${poly.name || ''}`}
              coordinates={poly.coordinates}
              strokeColor={strokeColor}
              fillColor={fillColor}
              strokeWidth={2}
            />
          );
        })}
        {markers.map((marker, idx) => (
          <Marker
            key={`${marker.title}-${idx}-${marker.latitude}-${marker.longitude}`}
            coordinate={{ latitude: marker.latitude, longitude: marker.longitude }}
            title={marker.title}
            pinColor={marker.color}
          />
        ))}
      </MapView>

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
  map: {
    minHeight: 320,
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
