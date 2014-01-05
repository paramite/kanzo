#!/usr/bin/env bash

git reset --hard
git status -s | grep "." && ( echo "Contains unknown files" ; exit 1 )

if [ "$1" = "final" ] ; then
    SNAPTAG=""
elif [ "$1" = "candidate" ] ; then
    SNAPTAG="rc"
else
    SNAPTAG=$(git log --oneline --no-merges | wc -l)
fi

python setup.py setopt -o tag_build -s "$SNAPTAG" -c egg_info
python setup.py sdist
