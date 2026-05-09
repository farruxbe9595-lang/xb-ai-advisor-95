import compileall, sys
sys.exit(0 if compileall.compile_dir('app', force=True, quiet=1) else 1)
