GeoSpyTia is an intuitive Geographic Information System (GIS) application that empowers users to visualize, process, and analyze spatial data. Designed for both beginner and advanced users, it offers a suite of tools for geospatial operations, data management, and interactive visualization.

Features:
  - File Management:
  - Open and save raster (e.g., GeoTIFF) and vector (e.g., shapefiles) datasets.
  - Import data directly from a PostgreSQL/PostGIS database.

  - Geoprocessing Tools:
  - **Buffer:** Generate buffer zones around vector geometries.
  - **Clip:** Clip vector layers using another layer as a boundary.
  - **Intersect:** Extract intersecting regions between two vector layers.

  - Raster Analysis:
  - Compute indices like NDVI (Normalized Difference Vegetation Index), NDBI (Normalized Difference Built-up Index), and LST (Land Surface Temperature).
  - Perform Urban Heat Island (UHI) analysis using combined raster data inputs.

  - Visualization:
  - Dynamically render and update raster and vector layers on an interactive map canvas.
  - Add legends with custom color gradients for raster layers.

Requirements:
- Python 3.8+
- Dependencies:
  - rasterio
  - geopandas
  - numpy
  - matplotlib
  - PyQt5
  - psycopg2

Usage
1. Launch the application:
   bash
   python main.py
   
2. Use the menu bar for operations:
   - File: Open, save, or connect to a database.
   - Geoprocessing: Perform spatial operations like Buffer and Clip.
   - Toolbox: Calculate indices such as NDVI, NDBI, and LST.

3. Add and manage layers using the "Add Data" dropdown or toolbar icons.

4. Interact with layers via the "Table of Contents" for visibility toggling and custom options.

Known Issues
- Performance may degrade when handling very large raster datasets.
- Lack of support for advanced spatial queries in database mode.
- Limited error messages for database connectivity issues.

Contribution
We welcome contributions to enhance GeoSpyTia. To contribute:
1. Fork the repository.
2. Create a feature branch:
   bash
   git checkout -b feature-name
   
3. Submit a pull request with a detailed explanation of your changes.






