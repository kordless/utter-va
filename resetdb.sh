#!/bin/bash
# can take a parameter if needed for correct path
sqlite3 $1./xoviova.db < $1./schema.sql
