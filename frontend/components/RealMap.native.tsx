import { View, StyleSheet, Text } from 'react-native';
import MapView, { Marker, Polygon, Polyline, PROVIDER_DEFAULT } from 'react-native-maps';

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
  route?: Array<{ latitude: number; longitude: number }>;
  polygon?: Array<{ latitude: number; longitude: number }>;
  overlayTitle?: string;
  overlayText?: string;
};

export default function RealMap({
  region,
  markers = [],
  route = [],
  polygon = [],
  overlayTitle,
  overlayText,
}: RealMapProps) {
  return (
    <View style={styles.wrapper}>
      <MapView
        style={styles.map}
        provider={PROVIDER_DEFAULT}
        initialRegion={region}
        showsCompass
        showsScale
        showsMyLocationButton={false}
        toolbarEnabled={false}
      >
        {route.length > 1 && <Polyline coordinates={route} strokeWidth={5} strokeColor="#1e40af" />}
        {polygon.length > 2 && (
          <Polygon coordinates={polygon} strokeColor="rgba(30,64,175,0.85)" fillColor="rgba(30,64,175,0.12)" strokeWidth={2} />
        )}
        {markers.map((marker) => (
          <Marker
            key={`${marker.title}-${marker.latitude}-${marker.longitude}`}
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
