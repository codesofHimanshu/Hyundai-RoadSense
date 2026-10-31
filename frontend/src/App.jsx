import { useCallback, useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Polyline,
  Popup,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-routing-machine/dist/leaflet-routing-machine.css";
import "./App.css";

const API = "http://127.0.0.1:8000";

const DEMO_LATITUDE = 26.6337;
const DEMO_LONGITUDE = 92.8000;
const METERS_PER_LATITUDE_DEGREE = 111320;
const METERS_PER_LONGITUDE_DEGREE =
  111320 * Math.cos((DEMO_LATITUDE * Math.PI) / 180);
const SIMULATION_START_DISTANCE_M = 500;

// Predefined road-shaped demo path, expressed as east/north offsets
// from the hazard. Adjust these points to align the route with the
// road geometry visible in your OpenStreetMap area.
const ROUTE_OFFSETS_M = [
  { east: -35, north: -500 },
  { east: -35, north: -390 },
  { east: -25, north: -310 },
  { east: 35, north: -245 },
  { east: 60, north: -165 },
  { east: 35, north: -95 },
  { east: 0, north: -35 },
  { east: 0, north: 0 },
];

function offsetsToCoordinates(offsets) {
  return offsets.map(({ east, north }) => [
    DEMO_LATITUDE + north / METERS_PER_LATITUDE_DEGREE,
    DEMO_LONGITUDE + east / METERS_PER_LONGITUDE_DEGREE,
  ]);
}

const ROUTE_TO_HAZARD = offsetsToCoordinates(ROUTE_OFFSETS_M);
const PAST_HAZARD_POSITION = offsetsToCoordinates([
  { east: 0, north: 35 },
])[0];
const FULL_ROUTE = [...ROUTE_TO_HAZARD, PAST_HAZARD_POSITION];

function distanceBetweenCoordinates(a, b) {
  const earthRadiusM = 6371000;
  const lat1 = (a[0] * Math.PI) / 180;
  const lat2 = (b[0] * Math.PI) / 180;
  const dLat = ((b[0] - a[0]) * Math.PI) / 180;
  const dLon = ((b[1] - a[1]) * Math.PI) / 180;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * earthRadiusM * Math.asin(Math.sqrt(Math.min(1, h)));
}

function getPolylineLength(points) {
  return points.slice(1).reduce(
    (total, point, index) =>
      total + distanceBetweenCoordinates(points[index], point),
    0
  );
}

function interpolateAlongRoute(points, fraction) {
  if (points.length === 0) return [DEMO_LATITUDE, DEMO_LONGITUDE];
  if (fraction <= 0) return points[0];
  if (fraction >= 1) return points[points.length - 1];

  const segmentLengths = points.slice(1).map((point, index) =>
    distanceBetweenCoordinates(points[index], point)
  );
  const totalLength = segmentLengths.reduce((sum, length) => sum + length, 0);
  let targetDistance = totalLength * fraction;

  for (let i = 0; i < segmentLengths.length; i += 1) {
    const segmentLength = segmentLengths[i];
    if (targetDistance <= segmentLength) {
      const ratio = segmentLength === 0 ? 0 : targetDistance / segmentLength;
      return [
        points[i][0] + (points[i + 1][0] - points[i][0]) * ratio,
        points[i][1] + (points[i + 1][1] - points[i][1]) * ratio,
      ];
    }
    targetDistance -= segmentLength;
  }

  return points[points.length - 1];
}

function getVehicleRoutePosition(distanceRemaining, passedHazard) {
  if (passedHazard) return PAST_HAZARD_POSITION;

  const clampedDistance = Math.max(
    0,
    Math.min(SIMULATION_START_DISTANCE_M, distanceRemaining ?? SIMULATION_START_DISTANCE_M)
  );
  const progress =
    (SIMULATION_START_DISTANCE_M - clampedDistance) /
    SIMULATION_START_DISTANCE_M;

  return interpolateAlongRoute(ROUTE_TO_HAZARD, progress);
}

// Custom map markers
function createMarkerIcon(color, symbol) {
  return L.divIcon({
    className: "roadsense-map-marker-wrapper",
    html: `
      <div class="roadsense-map-marker" style="--marker-color:${color}">
        ${symbol}
      </div>
    `,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18],
  });
}

const hazardIcon = createMarkerIcon("#ff5964", "!");
const vehicleIcon = createMarkerIcon("#38d9ff", "B");

// Format values
function formatDistance(distance) {
  if (distance === null || distance === undefined) {
    return "--";
  }

  if (distance < 1000) {
    return `${Math.round(distance)} m`;
  }

  return `${(distance / 1000).toFixed(2)} km`;
}

function formatHazardType(type) {
  if (!type) return "Road hazard";

  return type
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatAge(minutes) {
  if (minutes === undefined || minutes === null) {
    return "Age unavailable";
  }

  if (minutes < 1) {
    return "Reported just now";
  }

  if (minutes < 60) {
    return `Reported ${Math.round(minutes)} min ago`;
  }

  return `Reported ${Math.round(minutes / 60)} hr ago`;
}

// Fit the map to the predefined route and reported hazards.
function MapAutoFit({ hazards }) {
  const map = useMap();

  useEffect(() => {
    const points = [
      ...FULL_ROUTE,
      ...(hazards || []).map((hazard) => [
        hazard.latitude,
        hazard.longitude,
      ]),
    ];

    if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), {
        padding: [45, 45],
        maxZoom: 16,
      });
    }
  }, [map, hazards]);

  return null;
}

function App() {
  const [hazards, setHazards] = useState([]);
  const [vehicle, setVehicle] = useState(null);

  const [backendConnected, setBackendConnected] = useState(false);
  const [loadingHazards, setLoadingHazards] = useState(false);
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [error, setError] = useState("");

  // Fetch nearby hazards from the backend.
  const fetchHazards = useCallback(async () => {
    try {
      const response = await fetch(
        `${API}/api/hazards/nearby?latitude=${DEMO_LATITUDE}&longitude=${DEMO_LONGITUDE}&radius_m=1000&max_age_hours=24`
      );

      if (!response.ok) {
        throw new Error("Unable to retrieve hazards.");
      }

      const data = await response.json();

      setHazards(data.hazards || []);
      setBackendConnected(true);
      setError("");
    } catch {
      setBackendConnected(false);
      setError(
        "Cannot connect to the backend. Check that FastAPI is running on port 8000."
      );
    }
  }, []);

  // Fetch Vehicle B's current simulation state.
  const fetchVehicle = useCallback(async () => {
    try {
      const response = await fetch(
        `${API}/api/simulation/vehicle-b`
      );

      if (!response.ok) {
        throw new Error("Unable to retrieve Vehicle B state.");
      }

      const data = await response.json();

      setVehicle(data);
      setBackendConnected(true);
    } catch {
      setBackendConnected(false);
    }
  }, []);

  // Refresh both data sources periodically.
  useEffect(() => {
    fetchHazards();
    fetchVehicle();

    const interval = setInterval(() => {
      fetchHazards();
      fetchVehicle();
    }, 1000);

    return () => clearInterval(interval);
  }, [fetchHazards, fetchVehicle]);

  // Start the simulated approach.
  async function startSimulation() {
    setSimulationLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API}/api/simulation/vehicle-b/start`,
        { method: "POST" }
      );

      if (!response.ok) {
        throw new Error("Could not start Vehicle B.");
      }

      await fetchVehicle();
    } catch {
      setError(
        "Could not start the simulation. Check the backend terminal."
      );
    } finally {
      setSimulationLoading(false);
    }
  }

  // Stop the simulated approach.
  async function stopSimulation() {
    setSimulationLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API}/api/simulation/vehicle-b/stop`,
        { method: "POST" }
      );

      if (!response.ok) {
        throw new Error("Could not stop Vehicle B.");
      }

      await fetchVehicle();
    } catch {
      setError("Could not stop the simulation.");
    } finally {
      setSimulationLoading(false);
    }
  }

  // Move Vehicle B along the predefined road-shaped polyline.
  // The backend distance is the simulation's countdown; this frontend
  // maps that progress onto the fixed route for demonstration purposes.
  const distance = vehicle?.distance_from_hazard_m ?? SIMULATION_START_DISTANCE_M;
  const vehiclePosition = getVehicleRoutePosition(
    distance,
    Boolean(vehicle?.passed_hazard)
  );

  const warningLevel = (
    vehicle?.warning_level || "NONE"
  ).toLowerCase().replaceAll("_", "-");

  const warningClass =
    warningLevel === "no-hazard"
      ? "warning-no-hazard"
      : `warning-${warningLevel}`;

  const warningTitle = {
    none: "No immediate warning",
    approaching: "ROAD HAZARD APPROACHING",
    advance: "ROAD HAZARD AHEAD",
    close: "HAZARD VERY CLOSE",
    passed: "HAZARD PASSED",
    "no-hazard": "No active hazard detected",
  }[warningLevel] || "RoadSense monitoring";

  const warningSymbol = {
    none: "✓",
    approaching: "!",
    advance: "!",
    close: "!",
    passed: "✓",
    "no-hazard": "?",
  }[warningLevel] || "✓";

  return (
    <main className="dashboard">
      {/* Header */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">H</div>

          <div>
            <h1>
              HYUNDAI <span>RoadSense</span>
            </h1>

            <p>CONNECTED ROAD AWARENESS</p>
          </div>
        </div>

        <div className="connection">
          <span
            className={`connection-dot ${
              backendConnected ? "" : "disconnected"
            }`}
          />

          {backendConnected
            ? "RoadSense connected"
            : "Backend disconnected"}
        </div>
      </header>

      {/* Introduction */}
      <section className="welcome">
        <div>
          <p className="eyebrow">
            CONNECTED VEHICLE DEMONSTRATION
          </p>

          <h2>Know what lies ahead.</h2>

          <p className="subtitle">
            Vehicle A reports a disturbance. Vehicle B receives
            an advisory.
          </p>
        </div>

        <div className="road-icon" aria-hidden="true">
          ↗
        </div>
      </section>

      {/* Summary cards */}
      <section className="summary">
        <article className="summary-card">
          <span className="card-label">REPORTED HAZARDS</span>
          <strong>{hazards.length}</strong>
          <span className="card-note">
            Active hazards within the search radius
          </span>
        </article>

        <article className="summary-card">
          <span className="card-label">VEHICLE B STATUS</span>

          <strong className="status-value">
            {vehicle?.running ? "Moving" : "Stopped"}
          </strong>

          <span className="card-note">
            {vehicle?.speed_kmh ?? 36} km/h simulated speed
          </span>
        </article>

        <article className="summary-card">
          <span className="card-label">REPORTED HAZARD</span>

          <strong>
            {hazards.length > 0
              ? formatHazardType(hazards[0].event_type)
              : "None"}
          </strong>

          <span className="card-note">
            {hazards.length > 0
              ? `Nearest: ${formatDistance(hazards[0].distance_m)}`
              : "No active nearby reports"}
          </span>
        </article>
      </section>

      {/* Vehicle B warning */}
      <section
        className={`vehicle-b-panel ${
          vehicle?.running ? "simulation-running" : ""
        }`}
      >
        <div className="vehicle-b-heading">
          <div>
            <p className="eyebrow">VEHICLE B · LIVE SIMULATION</p>

            <h2>Driver advisory</h2>

            <p>
              Simulated approach toward the demonstration hazard.
            </p>
          </div>

          <span className="simulation-badge">
            SIMULATION ONLY
          </span>
        </div>

        <div className={`driver-alert ${warningClass}`}>
          <div className="alert-symbol">
            {warningSymbol}
          </div>

          <div className="alert-content">
            <div className="alert-kicker">
              ROAD HAZARD DETECTION
            </div>

            <h3>{warningTitle}</h3>

            <p>
              {vehicle?.warning_message ||
                "Waiting for simulation data."}
            </p>
          </div>

          <div className="alert-distance">
            <strong>
              {formatDistance(
                vehicle?.distance_from_hazard_m
              )}
            </strong>

            <span>To demo hazard</span>
          </div>
        </div>

        <div className="simulation-controls">
          <div className="simulation-info">
            <strong>Vehicle B controls</strong>

            <span>
              Synthetic GPS · {vehicle?.speed_kmh ?? 36} km/h
              · Predefined road route
            </span>
          </div>

          <div className="simulation-buttons">
            <button
              className="start-button"
              onClick={startSimulation}
              disabled={
                simulationLoading ||
                !backendConnected ||
                Boolean(vehicle?.running)
              }
            >
              ▶ Start approach
            </button>

            <button
              className="stop-button"
              onClick={stopSimulation}
              disabled={
                simulationLoading ||
                !backendConnected ||
                !vehicle?.running
              }
            >
              ■ Stop
            </button>
          </div>
        </div>

        <p className="simulation-note">
          Prototype demonstration only. Warning thresholds and
          simulated coordinates are not validated for real driving.
        </p>
      </section>

      {/* OpenStreetMap */}
      <section className="map-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">LIVE HAZARD VISUALIZATION</p>
            <h2>Road hazard map</h2>
          </div>

          <button
            onClick={() => {
              setLoadingHazards(true);

              fetchHazards().finally(() => {
                setLoadingHazards(false);
              });
            }}
            disabled={loadingHazards}
          >
            {loadingHazards ? "Refreshing..." : "↻ Refresh map"}
          </button>
        </div>

        <div className="map-legend">
          <span>
            <i className="legend-dot hazard-legend" />
            Reported hazard
          </span>

          <span>
            <i className="legend-dot vehicle-legend" />
            Vehicle B
          </span>
        </div>

        <div className="roadsense-map">
          <MapContainer
            center={[DEMO_LATITUDE, DEMO_LONGITUDE]}
            zoom={15}
            scrollWheelZoom
            className="leaflet-map"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {/* Fixed, predefined road-shaped route for the demo */}
            <Polyline
              positions={FULL_ROUTE}
              pathOptions={{
                color: "#38d9ff",
                weight: 5,
                opacity: 0.85,
                dashArray: "10 8",
              }}
            />

            {/* Reported hazard markers */}
            {hazards.map((hazard) => (
              <Marker
                key={hazard.id}
                position={[
                  hazard.latitude,
                  hazard.longitude,
                ]}
                icon={hazardIcon}
              >
                <Popup>
                  <div className="map-popup">
                    <strong>
                      {formatHazardType(hazard.event_type)}
                    </strong>

                    <p>
                      Confidence:{" "}
                      {Math.round(
                        (hazard.confidence ?? 0) * 100
                      )}
                      %
                    </p>

                    <p>
                      Source: {hazard.source_vehicle}
                    </p>

                    <p>
                      Distance from demo point:{" "}
                      {formatDistance(
                        hazard.distance_m
                      )}
                    </p>

                    <p>
                      {formatAge(hazard.age_minutes)}
                    </p>
                  </div>
                </Popup>
              </Marker>
            ))}

            {/* Vehicle B marker */}
            {vehicle && (
              <Marker
                position={vehiclePosition}
                icon={vehicleIcon}
              >
                <Popup>
                  <div className="map-popup">
                    <strong>Vehicle B</strong>

                    <p>
                      Status:{" "}
                      {vehicle.running ? "Moving" : "Stopped"}
                    </p>

                    <p>
                      Distance to demo hazard:{" "}
                      {formatDistance(
                        vehicle.distance_from_hazard_m
                      )}
                    </p>

                    <p>
                      Warning: {vehicle.warning_level}
                    </p>
                  </div>
                </Popup>
              </Marker>
            )}

            <MapAutoFit hazards={hazards} />
          </MapContainer>
        </div>

        <p className="map-note">
          The cyan dashed line is a predefined, road-shaped demonstration
          route. Vehicle B follows this path using synthetic position data;
          the route is manually configured and is not automatically matched
          to verified road centerlines.
        </p>
      </section>

      <footer>
        <span>Hyundai RoadSense · Prototype</span>
        <span>
          OpenStreetMap · FastAPI · React · SQLite
        </span>
      </footer>
    </main>
  );
}

export default App;