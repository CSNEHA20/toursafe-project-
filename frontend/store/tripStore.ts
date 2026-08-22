/**
 * TourSafe Trip & Itinerary Store (Zustand)
 * Manages tourist trips, active trip lifecycle, destinations, and itinerary waypoints.
 */

import { create } from "zustand";
import { touristApi } from "@/lib/api";
import type { TouristTrip, TripItineraryItem, TripItineraryStop } from "@/types";

interface TripStoreState {
  trips: TouristTrip[];
  activeTrip: TouristTrip | null;
  upcomingTrips: TouristTrip[];
  completedTrips: TouristTrip[];
  itineraries: TripItineraryItem[];
  loading: boolean;
  isLoading: boolean;
  error: string | null;

  setTrips: (trips: TouristTrip[]) => void;
  setActiveTrip: (trip: TouristTrip | null) => void;
  setItineraries: (itineraries: TripItineraryItem[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  fetchTrips: () => Promise<void>;
  createTrip: (data: {
    title: string;
    destination: string;
    start_date: string;
    end_date: string;
    notes?: string;
    description?: string;
    status?: string;
    stops?: TripItineraryStop[];
  }) => Promise<TouristTrip | null>;
  completeActiveTrip: () => Promise<boolean>;
  addItineraryEntry: (itineraryId: string, stop: TripItineraryStop) => Promise<boolean>;
  addStopToTrip: (tripId: string, stop: TripItineraryStop) => Promise<boolean>;
  reset: () => void;
}

export const useTripStore = create<TripStoreState>((set, get) => ({
  trips: [],
  activeTrip: null,
  upcomingTrips: [],
  completedTrips: [],
  itineraries: [],
  loading: false,
  isLoading: false,
  error: null,

  setTrips: (trips) => {
    const active = trips.find((t) => t.status === "active") || null;
    const upcoming = trips.filter((t) => t.status === "upcoming");
    const completed = trips.filter((t) => t.status === "completed");
    set({
      trips,
      activeTrip: active,
      upcomingTrips: upcoming,
      completedTrips: completed,
    });
  },

  setActiveTrip: (activeTrip) => set({ activeTrip }),
  setItineraries: (itineraries) => set({ itineraries }),
  setLoading: (loading) => set({ loading, isLoading: loading }),
  setError: (error) => set({ error }),

  fetchTrips: async () => {
    set({ loading: true, isLoading: true, error: null });
    try {
      const res = await touristApi.getMyItinerary();
      const rawItems: any[] = res.data?.items || res.data || [];

      const mappedTrips: TouristTrip[] = rawItems.map((item) => ({
        id: item.id || item._id || item.itinerary_id || `trip_${Date.now()}`,
        trip_id: item.itinerary_id || item.id,
        tourist_id: item.tourist_id || "tourist_me",
        title: item.title || item.destination || "Trip",
        destination: item.destination || item.title || "Destination",
        start_date: item.start_date || new Date().toISOString(),
        end_date: item.end_date || new Date(Date.now() + 86400000).toISOString(),
        notes: item.notes || item.description,
        description: item.description || item.notes,
        status: (item.status as any) || "active",
        itinerary_stops: item.stops || item.entries || item.itinerary_stops || [],
        created_at: item.created_at,
        updated_at: item.updated_at,
      }));

      get().setTrips(mappedTrips);
    } catch (err: any) {
      set({ error: err?.message || "Failed to fetch itineraries" });
    } finally {
      set({ loading: false, isLoading: false });
    }
  },

  createTrip: async (data) => {
    set({ loading: true, isLoading: true, error: null });
    try {
      const payload = {
        title: data.title,
        destination: data.destination,
        start_date: data.start_date,
        end_date: data.end_date,
        notes: data.notes || data.description,
        description: data.description || data.notes,
        status: data.status || "active",
        stops: data.stops || [],
      };

      const res = await touristApi.createItinerary(payload);
      const createdItem = res.data;

      const newTrip: TouristTrip = {
        id: createdItem?.id || createdItem?._id || `trip_${Date.now()}`,
        trip_id: createdItem?.id,
        tourist_id: createdItem?.tourist_id || "tourist_me",
        title: data.title,
        destination: data.destination,
        start_date: data.start_date,
        end_date: data.end_date,
        notes: data.notes || data.description,
        description: data.description || data.notes,
        status: "active",
        itinerary_stops: data.stops || [],
        created_at: new Date().toISOString(),
      };

      const current = get().trips;
      get().setTrips([newTrip, ...current]);
      return newTrip;
    } catch (err: any) {
      set({ error: err?.message || "Failed to create trip" });
      throw err;
    } finally {
      set({ loading: false, isLoading: false });
    }
  },

  completeActiveTrip: async () => {
    const active = get().activeTrip;
    if (!active) return false;

    set({ loading: true, isLoading: true });
    try {
      if (active.id) {
        try {
          await touristApi.updateMyItinerary({
            status: "completed",
          });
        } catch {
          // Fallback local update
        }
      }

      const updated = get().trips.map((t) =>
        t.id === active.id ? { ...t, status: "completed" as const } : t
      );
      get().setTrips(updated);
      return true;
    } catch (err: any) {
      set({ error: err?.message || "Failed to complete trip" });
      return false;
    } finally {
      set({ loading: false, isLoading: false });
    }
  },

  addItineraryEntry: async (itineraryId, stop) => {
    try {
      const current = get().trips;
      const updated = current.map((t) => {
        if (t.id === itineraryId || t.trip_id === itineraryId) {
          const stops = t.itinerary_stops || [];
          return { ...t, itinerary_stops: [...stops, stop] };
        }
        return t;
      });
      get().setTrips(updated);
      return true;
    } catch (err: any) {
      set({ error: err?.message || "Failed to add stop" });
      return false;
    }
  },

  addStopToTrip: async (tripId, stop) => {
    return get().addItineraryEntry(tripId, stop);
  },

  reset: () => {
    set({
      trips: [],
      activeTrip: null,
      upcomingTrips: [],
      completedTrips: [],
      itineraries: [],
      loading: false,
      isLoading: false,
      error: null,
    });
  },
}));
