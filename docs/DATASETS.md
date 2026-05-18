# Datasets

Every dataset earns its place by answering a specific question the project must answer. Don't add datasets not listed here without a documented reason.

---

## Quick reference

| Dataset | GEE asset ID | Latency | Resolution | Role |
|---|---|---|---|---|
| JRC Global Surface Water | `JRC/GSW1_4/MonthlyHistory` | 12–18 months | 30m, monthly, 1984–2024 | Historical backbone |
| Sentinel-2 SR Harmonized | `COPERNICUS/S2_SR_HARMONIZED` | 2–5 days | 10m, 5-day revisit | Live area |
| Sentinel-1 GRD (SAR) | `COPERNICUS/S1_GRD` | 3–6 days | 10m, 6–12 day revisit | Monsoon cloud fallback |
| SRTM DEM | `USGS/SRTMGL1_003` | Static | 30m | Area-volume curves |
| CHIRPS Daily Rainfall | `UCSB-CHG/CHIRPS/DAILY` | 1–3 days | ~5km daily | Catchment rainfall (Phase 2+) |
| WorldPop | `WorldPop/GP/100m/pop` | Static (2020) | 100m | Population served |
| HydroSHEDS Basins | `WWF/HydroSHEDS/v1/Basins/hybas_8` | Static | Sub-basin polygons | Catchment definition |
| GRACE | `NASA/GRACE/MASS_GRIDS_V04/LAND` | 1–2 months | ~25,000 km² | Phase 5 only |

External (non-GEE):

| Source | URL | Latency | Role |
|---|---|---|---|
| CWC Reservoir Bulletin | `http://cwc.gov.in/reservoir-bulletin` | Weekly (Thursdays) | Ground truth |
| NOAA ONI | `https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php` | Monthly | El Niño signal |
| IMD Long Range Forecast | `https://mausam.imd.gov.in` | Seasonal | Monsoon outlook (qualitative) |

---

## JRC Global Surface Water — the foundation

**What it is:** Per-pixel monthly water/no-water classification for every Landsat-observable pixel on Earth, from March 1984 to December 2024. Peer-reviewed (Pekel et al. 2016 Nature). Already validated globally.

**What it gives us:** A pre-computed 40-year time series of water extent per pixel. We aggregate over each reservoir's AOI to get a monthly area-in-km² series. Zero preprocessing.

**Why it matters here:** Without JRC we'd build this from scratch with raw Landsat, which is doable but eats weeks. JRC compresses that into a one-line `ee.ImageCollection` call.

**Limitation:** Ends Dec 2024 (~18 month lag). We stitch Sentinel-2 onto it for 2025–present.

**The sediment story it enables (Phase 2+ chart):** JRC's `permanent` and `seasonal` water bands let us see how each reservoir's full-pool area has shrunk over 40 years due to sedimentation. Almost nobody has visualized this for Indian reservoirs at scale. Original-finding territory.

### Code pattern

```python
jrc = ee.ImageCollection('JRC/GSW1_4/MonthlyHistory')
def area_in_aoi(image, aoi):
    return image.select('water').eq(2).multiply(ee.Image.pixelArea()).divide(1e6) \
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=30).get('water')
```

---

## Sentinel-2 SR Harmonized — the live layer

**What it is:** Surface reflectance imagery from the Sentinel-2 A/B satellites, 5-day revisit, 10m resolution, harmonized across the constellation. Available in GEE within ~2–5 days of capture.

**What it gives us:** Current reservoir extent, with enough freshness to claim "as of last week" honestly.

**Method:** 30-day median composite, cloud-masked via SCL band, MNDWI threshold > 0 for water. Mask hillshade with SRTM slope < 10° to avoid false water on shadowed terrain.

**Limitation:** Monsoon cloud cover. June–September can have 70%+ cloud over reservoirs. Sentinel-1 covers that.

### MNDWI

`MNDWI = (B3 - B11) / (B3 + B11)`, threshold > 0.

This is better than NDWI for reservoirs because B11 (SWIR) is more sensitive to turbid water — important for sediment-laden Indian reservoirs.

### Code pattern

```python
def s2_water_area(aoi, end_date, days=30):
    start = end_date - timedelta(days=days)
    coll = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(aoi)
        .filterDate(start, end_date)
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 80)))

    def mask_clouds(img):
        scl = img.select('SCL')
        cloud_mask = scl.neq(8).And(scl.neq(9)).And(scl.neq(10))
        return img.updateMask(cloud_mask)

    composite = coll.map(mask_clouds).median()
    mndwi = composite.normalizedDifference(['B3', 'B11'])
    water = mndwi.gt(0)
    # Slope mask
    slope = ee.Terrain.slope(ee.Image('USGS/SRTMGL1_003'))
    water = water.updateMask(slope.lt(10))
    area = water.multiply(ee.Image.pixelArea()).divide(1e6) \
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=10)
    return area.get('nd')
```

---

## Sentinel-1 SAR — the monsoon fallback

**What it is:** Synthetic Aperture Radar imagery, cloud-immune. 6–12 day revisit at 10m. We use the GRD (Ground Range Detected) product.

**When to use:** When Sentinel-2 cloud cover over the AOI exceeds 70% in the last 30 days.

**Method:** VV polarization, threshold backscatter < -15 dB → water. Speckle filter (refined Lee or 5x5 median) first.

**Limitation:** SAR detects water-like surfaces, which can include wet mud, paddy fields, and some bare earth. False positives in monsoon. We accept this; we flag `data_source: "sentinel_1"` and widen confidence intervals.

**Why we cut this from the hackathon version:** Coregistration and speckle filtering have edge cases that eat a weekend. With agents, this is one of the first stretch tasks.

### Code pattern

```python
def s1_water_area(aoi, end_date, days=30):
    start = end_date - timedelta(days=days)
    coll = (ee.ImageCollection('COPERNICUS/S1_GRD')
        .filterBounds(aoi)
        .filterDate(start, end_date)
        .filter(ee.Filter.eq('instrumentMode', 'IW'))
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
        .select('VV'))
    # Speckle filter — refined Lee or simple median
    composite = coll.median().focal_median(50, 'circle', 'meters')
    water = composite.lt(-15)
    area = water.multiply(ee.Image.pixelArea()).divide(1e6) \
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=10)
    return area.get('VV')
```

---

## SRTM DEM — area-to-volume conversion

**What it is:** Shuttle Radar Topography Mission, 30m global DEM.

**What it gives us:** Elevation grid under each reservoir. By assuming the reservoir basin is approximated by the bowl-shape SRTM saw before impoundment, we can build a hypsometric (elevation-area) curve, which by integration gives an elevation-volume curve. Combined with our water-surface elevation (inferred from area), this estimates volume.

**Limitation:** For reservoirs built before SRTM (2000), the basin floor is underwater and the DEM is incorrect there. Most major Indian reservoirs predate 2000. We calibrate against CWC reported volumes to absorb this systematic error.

**The calibration:**

1. Build a candidate hypsometric curve from SRTM.
2. Pull historical area + CWC volume pairs (where both exist).
3. Fit `V = a × A^b` (power law) — typical reservoir geometry.
4. Validate: r² > 0.85 required. If not, flag the reservoir as `low_volume_confidence`.

### Code pattern

```python
def fit_hypsometric_curve(aoi, cwc_volumes_by_date, satellite_areas_by_date):
    """
    cwc_volumes_by_date: dict[date, float_bcm]
    satellite_areas_by_date: dict[date, float_km2]
    Returns: (a, b, r_squared)
    """
    matched = [
        (satellite_areas_by_date[d], cwc_volumes_by_date[d])
        for d in cwc_volumes_by_date if d in satellite_areas_by_date
    ]
    A = np.array([m[0] for m in matched])
    V = np.array([m[1] for m in matched])
    # Power law fit in log space
    log_A = np.log(A)
    log_V = np.log(V)
    b, log_a = np.polyfit(log_A, log_V, 1)
    a = np.exp(log_a)
    pred = a * A ** b
    r2 = 1 - np.sum((V - pred)**2) / np.sum((V - V.mean())**2)
    return a, b, r2
```

---

## CWC Weekly Bulletin — ground truth

**What it is:** Central Water Commission's weekly PDF reporting live storage, percent of FRL, percent of normal for 166 reservoirs.

**Where:** Published Thursdays at http://cwc.gov.in/reservoir-bulletin.

**Why it matters:** Official ground truth. Anchors our area-to-volume curves. When our satellite-derived estimate disagrees with CWC, CWC wins for the displayed `cwc_reported_bcm` field; we still show our `estimated_storage_bcm`.

**Scraping:** PDF format, regex-based. Fragile — format changes ~annually. The scraper has a single responsibility: produce a clean `pd.DataFrame` with `reservoir_id, date, live_storage_bcm, percent_frl, percent_normal`. If parsing fails, raise a clear `CWCFormatError`. Do not silently produce garbage.

### Reservoir ID matching

CWC names don't always match ours cleanly (e.g. "Krishna Raja Sagar" vs "KRS"). Maintain a `cwc_name_aliases.csv` mapping CWC's official name to our reservoir ID.

---

## NOAA ONI — the El Niño signal

**What it is:** Oceanic Niño Index. Monthly running mean of sea surface temperature anomalies in the Niño 3.4 region of the Pacific.

**Source:** `https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php` — a simple text/CSV file.

**Why:** The El Niño projection scenario depends on classifying the current and forecast ENSO state.

**Classification:**

```python
def classify_enso(oni: float, trend_3mo: float) -> str:
    if oni > 0.5:
        return "el_nino_developing" if trend_3mo > 0 else "el_nino"
    elif oni < -0.5:
        return "la_nina_developing" if trend_3mo < 0 else "la_nina"
    return "neutral"
```

### Historical El Niño years for India

Used to compute per-reservoir El Niño inflow delta:

- Strong: 1982-83, 1997-98, 2015-16, 2023-24
- Moderate: 1986-87, 1991-92, 2002-03, 2009-10
- Weak/borderline: 2018-19

Neutral and La Niña years are computed as everything else (with La Niña separated for completeness even if we don't model it specifically).

---

## CHIRPS — catchment rainfall (Phase 2+)

**What it is:** Climate Hazards Group InfraRed Precipitation with Station data. 5km daily rainfall, 1981–present, ~3 day latency.

**Why:** Lets us project actual inflow during the monsoon rather than pure depletion extrapolation. By computing rainfall over each reservoir's catchment (HydroSHEDS basin polygons), we can estimate expected refill once the monsoon hits.

**Used in:** Phase 2+ as a secondary projection input. Pure depletion-rate projection still shown alongside.

---

## HydroSHEDS Basins — catchment definition

**What it is:** Hierarchical hydrological basins at multiple levels.

**Use:** Level 8 (`hybas_8`) gives sub-basin polygons of appropriate size (~1000–10,000 km²) to use as each reservoir's catchment. Used as the area over which we aggregate CHIRPS rainfall.

---

## WorldPop — population served

**What it is:** Gridded population estimates at 100m, India.

**Why:** Drives the "X million people served" headline number per reservoir.

**Limitation:** 2020 baseline. India's population has grown since, but the relative distribution is approximately correct. Don't make per-village claims.

**Method:** Manual lookup per reservoir of the city/cities it serves; population values stored in `reservoirs.csv`. Not computed at pipeline time.

---

## GRACE (Phase 5 only)

**What it is:** Gravity Recovery and Climate Experiment satellites measure changes in Earth's gravity field, which translate to changes in water mass — including groundwater.

**Why interesting:** Surface water tells you what's in the buckets (reservoirs). GRACE tells you what's in the underground aquifer. Together they describe India's full freshwater stress.

**Why deferred:** Different technical project. Resolution is very coarse (25,000 km²). Best paired with a different methodology.

**If pursued:** Treat as a separate sub-project with its own phase 0–4.

---

## What we explicitly don't use

Don't go looking for these; they're not in scope.

- **Landsat raw scenes.** JRC has already digested Landsat for water. Re-processing it from raw is wasted effort.
- **MODIS water products.** Too coarse for individual reservoirs.
- **VIIRS DNB nighttime lights.** Useful for other projects, not this one.
- **GHSL built-up surface.** WorldPop covers population; we don't need built-up area.
- **Hansen Global Forest Change.** Not relevant to reservoirs.
- **ECMWF ERA5.** CHIRPS is sufficient for rainfall; ERA5 adds complexity without insight here.

If you find yourself wanting to add a dataset not in the matrix above, write to `IDEAS.md` first.
