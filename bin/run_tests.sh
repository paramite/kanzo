#!/bin/bash

SCRIPT_PATH="${BASH_SOURCE[0]}";
if ([ -h "${SCRIPT_PATH}" ]) then
  while([ -h "${SCRIPT_PATH}" ]) do cd `dirname "$SCRIPT_PATH"`; SCRIPT_PATH=`readlink "${SCRIPT_PATH}"`; done
fi
cd "`dirname ${SCRIPT_PATH}`/.." > /dev/null
PROJECT_PATH=`pwd`;

export KANZO_PROJECT="${PROJECT_PATH}/tests/test_project.py"
nosetests --verbosity=2 --with-coverage --cover-erase --cover-package=kanzo -w $PROJECT_PATH
