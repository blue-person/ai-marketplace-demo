CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O0 -g -fno-stack-protector
LDFLAGS  ?= -no-pie
LDLIBS   := -lcurl

robot: src/robot.cpp
	$(CXX) $(CXXFLAGS) $< -o $@ $(LDFLAGS) $(LDLIBS)

clean:
	rm -f robot

.PHONY: clean
