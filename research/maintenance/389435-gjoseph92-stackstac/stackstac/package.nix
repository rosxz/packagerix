{ lib
, python3Packages
, fetchFromGitHub
}:

python3Packages.buildPythonApplication rec {
  pname = "stackstac";
  version = "0.5.1";

  src = fetchFromGitHub {
    owner = "gjoseph92";
    repo = "stackstac";
    rev = "v${version}";
    hash = "sha256-7mll2jiZEx0xPDATWCBgqle4I68pkL6BeTLHKRmXEss=";
  };

  pyproject = true;

  buildInputs = with python3Packages; [
    pdm-pep517
  ];

  propagatedBuildInputs = with python3Packages; [
    dask
    numpy
    pandas
    pyproj
    rasterio
    xarray
    pystac-client
    gdal  # Added as recommended for geospatial operations
  ];

  nativeCheckInputs = with python3Packages; [
    pytestCheckHook
    hypothesis
  ];

  disabledTestPaths = [
    "stackstac/tests/test_stac_types.py"
    "stackstac/tests/test_to_dask.py"
  ];

  doInstallCheck = true;
  installCheckPhase = ''
    python -c "import stackstac; print(stackstac.__version__)"
  '';

  pythonImportsCheck = [ pname ];
}