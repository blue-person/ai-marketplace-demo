CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wformat=2 -Werror=format-security -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=3 \
            -D_GLIBCXX_ASSERTIONS -fstack-clash-protection -fstack-protector-strong -fcf-protection=full -fPIE
LDFLAGS  ?= -pie -Wl,-z,noexecstack -Wl,-z,relro -Wl,-z,now -Wl,--as-needed -Wl,--no-copy-dt-needed-entries
LDLIBS   := -lcurl

robot: src/robot.cpp
	$(CXX) $(CXXFLAGS) $< -o $@ $(LDFLAGS) $(LDLIBS)

clean:
	rm -f robot

.PHONY: clean
