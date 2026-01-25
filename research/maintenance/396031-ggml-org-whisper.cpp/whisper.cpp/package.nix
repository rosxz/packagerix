{ lib
, stdenv
, fetchFromGitHub
, cmake
, git
, cudaPackages ? null
, vulkan-loader ? null
, openblas ? null
, sdl2 ? null
, ffmpeg ? null
, cudaSupport ? false
, vulkanSupport ? false
, openblasSupport ? false
, sdlSupport ? false
, ffmpegSupport ? false
}:

let
  inherit (lib) optionals optional optionalString;
in
stdenv.mkDerivation rec {
  pname = "whisper.cpp";
  version = "1.7.6";

  src = fetchFromGitHub {
    owner = "ggml-org";
    repo = "whisper.cpp";
    rev = "v${version}";
    hash = "sha256-dppBhiCS4C3ELw/Ckx5W0KOMUvOHUiisdZvkS7gkxj4=";
  };

  nativeBuildInputs = [ cmake git ]
    ++ optionals cudaSupport [ cudaPackages.cuda_nvcc ]
    ++ optionals vulkanSupport [ vulkan-loader ]
    ++ optionals sdlSupport [ sdl2 ]
    ++ optionals ffmpegSupport [ ffmpeg ];

  buildInputs = optionals openblasSupport [ openblas ]
    ++ optionals cudaSupport [ cudaPackages.libcublas ]
    ++ optionals vulkanSupport [ vulkan-loader ]
    ++ optionals sdlSupport [ sdl2 ]
    ++ optionals ffmpegSupport [ ffmpeg ];

  dontUseCmakeBuildDir = true;

  cmakeFlags = [
    "-DCMAKE_INSTALL_PREFIX=${placeholder "out"}"
    "-DCMAKE_BUILD_TYPE=Release"
  ] ++ optionals cudaSupport [
    "-DGGML_CUDA=1"
  ] ++ optionals vulkanSupport [
    "-DGGML_VULKAN=1"
  ] ++ optionals openblasSupport [
    "-DGGML_OPENBLAS=1"
  ] ++ optionals sdlSupport [
    "-DGGML_SDL=1"
  ] ++ optionals ffmpegSupport [
    "-DGGML_FFMPEG=1"
  ];

  buildPhase = ''
    cmake -B build ${toString cmakeFlags} -DCMAKE_SKIP_BUILD_RPATH=ON -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON
    cmake --build build -j $NIX_BUILD_CORES
  '';

  installPhase = ''
    mkdir -p $out/bin
    cp build/bin/main $out/bin/whisper-main
    cp build/bin/whisper-cli $out/bin/whisper-cli
    cp build/bin/whisper-server $out/bin/whisper-server
  '';
}