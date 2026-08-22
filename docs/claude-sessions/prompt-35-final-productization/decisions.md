# Prompt 35 — Key Decisions

## Architectural & UX Design Decisions

### 1. Unified Entry Gateway vs Role-Partitioned Subdomains
- **Decision**: Implemented a unified root entry portal (`frontend/app/index.tsx`) with automatic active session detection and explicit role gateway routing, rather than hardcoded role partitioning.
- **Rationale**: In government operations, supervisors often inspect both the centralized dispatcher command center and field responder views during tactical debriefs. The unified portal provides clear persona entry points while honoring active JWT sessions.

### 2. Standardizing on `lucide-react-native`
- **Decision**: Completely replaced legacy `@expo/vector-icons` Ionicons and MaterialCommunityIcons with `lucide-react-native`.
- **Rationale**: Vector icons that rely on custom TTF font loading frequently experience hydration mismatch flashes on web export and require platform-specific font linking on native. Lucide renders pure SVGs, providing razor-sharp visual clarity and zero hydration artifacts across Web, iOS, and Android.

### 3. Separation of Unit Testing from React Native UI Bundling
- **Decision**: Structured automated frontend tests to validate pure kinematics algorithms, sampling frequencies, sliding buffers, and geospatial Haversine math using Node's native test runner (`tsx --test`), avoiding unbundled React Native JSX dependencies.
- **Rationale**: Running unit tests directly through `tsx --test` provides lightning-fast (<2s) CI/CD execution and eliminates brittle mockings of mobile UI layout contexts.

### 4. B2G Color Palette and High-Density Typography
- **Decision**: Strictly adhered to the established TourSafe government tokens: Deep Navy (`#0B132B`, `#1A3C6E`), Indian Saffron (`#FF6B00`), Forest Emerald (`#046A38`), Teal (`#0D7680`), and Crimson Alert (`#C53030`).
- **Rationale**: Ensures high visual contrast and calm authority suitable for official multi-monitor 24/7 command centers.
