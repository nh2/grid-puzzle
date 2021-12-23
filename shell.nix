{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "python-with-gtk";

  nativeBuildInputs = with pkgs; [
    gobject-introspection
  ];

  buildInputs = with pkgs; [
    gtk3
    (python3.withPackages (ps: with ps; [
      pygobject3
    ]))
  ];
}
