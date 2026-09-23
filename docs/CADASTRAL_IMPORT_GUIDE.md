# LandGuard cadastral import

LandGuard no longer creates demo parcel rectangles. The ownership layer remains empty until a real cadastral GeoJSON file is imported for the selected project.

## Source workflow

1. Use Odisha **BhuNaksha** to inspect the cadastral map and plot geometry reference.
2. Use Odisha **Bhulekh/RoR** to validate plot/Khata/land-record attributes.
3. Obtain an authorised departmental cadastral export (or convert the approved GIS dataset) to **GeoJSON in EPSG:4326 / WGS84**.
4. In **GIS Map → Land record layer**, select the project and choose **Import cadastral GeoJSON**.
5. Enable **Authority-verified export** only when the file provenance has been confirmed.

LandGuard does not scrape BhuNaksha map geometry and does not classify government/private land from satellite appearance.

## GeoJSON properties

Each feature must be a `Polygon` or `MultiPolygon`. Recommended properties:

```json
{
  "plot_no": "245",
  "khata_no": "73",
  "unique_plot_id": "<authority unique plot id>",
  "ownership_type": "PRIVATE",
  "kisam": "<land class>",
  "village": "<village>",
  "tahasil": "<tahasil>",
  "area_acres": 0.84,
  "source_record_id": "<optional record id>"
}
```

Accepted `ownership_type` values are `GOVERNMENT`, `PRIVATE`, `GOVERNMENT_LEASEHOLD`, `INSTITUTIONAL`, and `UNKNOWN`. A few direct textual synonyms are normalized, but LandGuard never guesses ownership from plot shape, land use, Khata number, or imagery.

If `area_acres` is absent, LandGuard estimates polygon area from WGS84 coordinates for dashboard summarisation.
