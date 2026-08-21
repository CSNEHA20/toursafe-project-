import { Platform } from 'react-native';

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

export default function RealMap(props: RealMapProps) {
  const implementation =
    Platform.OS === 'web' ? require('./RealMap.web').default : require('./RealMap.native').default;

  return implementation(props);
}
