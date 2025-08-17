#!/bin/bash

# Parcours récursif de tous les fichiers *.gz
find . -type f -name "*.gz" | while read -r file; do
    echo "Décompression de $file"
    gzip -d "$file"
done

echo "Terminé."
