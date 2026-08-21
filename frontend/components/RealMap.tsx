import { Platform } from 'react-native';

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

export default function RealMap(props: RealMapProps) {
  const implementation =
    Platform.OS === 'web' ? require('./RealMap.web').default : require('./RealMap.native').default;

  return implementation(props);
}
