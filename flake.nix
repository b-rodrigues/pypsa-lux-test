{
  description = "Luxembourg Energy Transition Simulator (Shiny + PyPSA + Polars)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        pythonPackages = pkgs.python3Packages;

        linopy = pythonPackages.buildPythonPackage rec {
          pname = "linopy";
          version = "0.10.1";
          format = "wheel";
          src = pkgs.fetchurl {
            url = "https://files.pythonhosted.org/packages/8f/82/f54c36317a66e7de073711c01969453bbd244c145b866f025474f7d8bd1b/linopy-${version}-py3-none-any.whl";
            sha256 = "1a02e4aa0b7dedccdd93ea4d5c7e84139d5b00d7630f4058d12f1805e8cc3cf4";
          };
          propagatedBuildInputs = with pythonPackages; [
            numpy
            scipy
            bottleneck
            toolz
            numexpr
            xarray
            dask
            polars
            tqdm
            deprecation
            packaging
          ];
          doCheck = false;
          dontCheckRuntimeDeps = true;
        };

        pypsa = pythonPackages.buildPythonPackage rec {
          pname = "pypsa";
          version = "1.4.0";
          format = "wheel";
          src = pkgs.fetchurl {
            url = "https://files.pythonhosted.org/packages/18/58/07c88fdd7a7f5041936e439f0e26a8904470ec55db5059ebc6980dfab227/pypsa-${version}-py3-none-any.whl";
            sha256 = "216d00376f82b3c8d6d19747bcc868bfaa634befcf34d1564ad0730984f448d1";
          };
          propagatedBuildInputs = with pythonPackages; [
            numpy
            scipy
            pandas
            pyarrow
            xarray
            netcdf4
            linopy
            matplotlib
            plotly
            pydeck
            seaborn
            geopandas
            shapely
            networkx
            deprecation
            validators
            highspy
            rapidfuzz
            platformdirs
          ];
          doCheck = false;
          dontCheckRuntimeDeps = true;
        };

        pythonEnv = pkgs.python3.withPackages (
          ps: with ps; [
            polars
            shiny
            pypsa
            linopy
            highspy
            plotly
            matplotlib
            pyyaml
            pytest
          ]
        );
      in
      {
        packages.default = pythonEnv;

        devShells.default = pkgs.mkShell {
          name = "lux-energy-simulator-shell";
          packages = [
            pythonEnv
            pkgs.highs
          ];

          shellHook = ''
            echo "═══════════════════════════════════════════════════════════════════"
            echo " Luxembourg Energy Transition Simulator (PyPSA + Shiny + Polars) "
            echo " Python $(python --version 2>&1 | cut -d' ' -f2)"
            echo "═══════════════════════════════════════════════════════════════════"
            echo "Run dashboard: shiny run app.py --reload"
            echo "Run tests:     pytest"
            echo ""
          '';
        };
      }
    );
}
