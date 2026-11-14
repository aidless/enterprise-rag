.PHONY: demo demo-build demo-test eval

demo:
	python3 demo/server.py

demo-build:
	python3 demo/build_static.py

demo-test:
	python3 -m unittest demo/test_demo.py -v

eval:
	python3 eval/run_cases.py --save
	python3 -m unittest demo/test_demo.py
