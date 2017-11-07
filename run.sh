#!/bin/bash
  docker stop bitboard-rest
  docker rm bitboard-rest
  docker run -p 5000:5000 \
             --restart="unless-stopped" \
             --name bitboard-rest \
             -v $(pwd):/code \
             -it bitboard/rest python3 run.py