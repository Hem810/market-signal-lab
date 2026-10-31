#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace std;
vector<string> split(const string &s) {
    vector<string> v;
    string x;
    stringstream ss(s);
    while (getline(ss, x, ','))
        v.push_back(x);
    return v;
}
double num(const string &s) {
    size_t n;
    double x = stod(s, &n);
    if (n != s.size() || !isfinite(x))
        throw runtime_error("invalid number");
    return x;
}
struct Bar {
    string date, opents, closets, sym;
    double open, close;
};
struct Sig {
    string time, entry, sym;
    double weight;
};
vector<vector<string>> read(const string &path, const string &header, int n) {
    ifstream f(path);
    if (!f)
        throw runtime_error("cannot read " + path);
    string line;
    getline(f, line);
    if (line != header)
        throw runtime_error("schema mismatch");
    vector<vector<string>> rows;
    while (getline(f, line)) {
        auto v = split(line);
        if ((int)v.size() != n)
            throw runtime_error("field count");
        rows.push_back(v);
    }
    return rows;
}
int main(int argc, char **argv) {
    try {
        if (argc != 7)
            throw runtime_error("usage: simulator signals.csv market.csv output-prefix "
                                "commission-bps slippage-bps capital");
        double fee = num(argv[4]) / 10000, slip = num(argv[5]) / 10000, cash = num(argv[6]);
        if (fee < 0 || slip < 0 || fee + slip >= 1 || cash <= 0)
            throw runtime_error("invalid account config");
        double prev = cash;
        map<string, vector<Sig>> signals;
        set<pair<string, string>> seen;
        for (auto v :
             read(argv[1],
                  "version,run,model,fold,symbol,signal_ts,entry_ts,prediction,weight,volatility",
                  10)) {
            if (v[0] != "1" || v[5] >= v[6] || v[5].size() != 20 || v[6].size() != 20 ||
                v[5].back() != 'Z' || v[6].back() != 'Z')
                throw runtime_error("version/timing");
            num(v[7]);
            num(v[9]);
            double w = num(v[8]);
            if (w < 0 || w > .25 || !seen.insert({v[6], v[4]}).second)
                throw runtime_error("duplicate or invalid weight");
            signals[v[6]].push_back({v[5], v[6], v[4], w});
        }
        for (auto [t, ss] : signals) {
            double sum = 0;
            for (auto s : ss)
                sum += s.weight;
            if (sum > 1.00000001)
                throw runtime_error("leverage");
        }
        map<string, map<string, Bar>> days;
        seen.clear();
        for (auto v : read(argv[2], "session,open_ts,close_ts,symbol,open,close", 6)) {
            if (!seen.insert({v[0], v[3]}).second)
                throw runtime_error("duplicate market");
            double o = num(v[4]), c = num(v[5]);
            if (o <= 0 || c <= 0 || v[1] >= v[2])
                throw runtime_error("invalid market");
            days[v[0]][v[3]] = {v[0], v[1], v[2], v[3], o, c};
        }
        string prefix = argv[3];
        ofstream eq(prefix + "-equity.csv"), fills(prefix + "-fills.csv"),
            pos(prefix + "-positions.csv"), attr(prefix + "-attribution.csv");
        if (!eq || !fills || !pos || !attr)
            throw runtime_error("output unavailable");
        for (auto *f : {&eq, &fills, &pos, &attr})
            *f << setprecision(16);
        eq << "session,equity,cash,exposure,overnight,intraday,fees,slippage,turnover,residual,"
              "stale\n";
        fills
            << "session,symbol,signal_ts,execution_ts,requested,filled,price,fee,slippage,status\n";
        pos << "session,symbol,shares,mark,value\n";
        attr << "session,symbol,overnight,intraday,fees,slippage,pnl\n";
        map<string, long long> shares;
        map<string, double> marks;
        bool started = false;
        for (auto [date, bars] : days) {
            string open = bars.begin()->second.opents;
            for (auto [s, b] : bars)
                if (b.opents != open)
                    throw runtime_error("inconsistent session opens");
            if (!started && !signals.count(open))
                continue;
            started = true;
            double overnight = 0, intraday = 0, fees = 0, slippage = 0, traded = 0;
            int stale = 0;
            map<string, double> ov, in, fc, sc;
            double equityopen = cash;
            for (auto [s, q] : shares) {
                double p = marks[s];
                if (bars.count(s))
                    p = bars[s].open;
                else if (q)
                    stale++;
                ov[s] = q * (p - marks[s]);
                overnight += ov[s];
                equityopen += q * p;
            }
            vector<pair<Sig, long long>> orders;
            if (signals.count(open))
                for (auto s : signals[open]) {
                    if (!bars.count(s.sym)) {
                        fills << date << ',' << s.sym << ',' << s.time << ',' << open
                              << ",0,0,0,0,0,missing_open\n";
                        continue;
                    }
                    long long target = (long long)floor(s.weight * equityopen / bars[s.sym].open);
                    orders.push_back({s, target - shares[s.sym]});
                }
            stable_sort(orders.begin(), orders.end(), [](auto a, auto b) {
                if ((a.second < 0) != (b.second < 0))
                    return a.second < 0;
                return a.first.sym < b.first.sym;
            });
            for (auto [s, requested] : orders) {
                double p = bars[s.sym].open;
                long long q = requested;
                if (q > 0)
                    q = min(q, (long long)floor(max(0., cash) / (p * (1 + fee + slip))));
                else
                    q = max(q, -shares[s.sym]);
                double notional = abs(q) * p, f = notional * fee, sl = notional * slip;
                cash -= q * p + f + sl;
                shares[s.sym] += q;
                fees += f;
                slippage += sl;
                traded += notional;
                fc[s.sym] += f;
                sc[s.sym] += sl;
                if (requested)
                    fills << date << ',' << s.sym << ',' << s.time << ',' << open << ','
                          << requested << ',' << q << ',' << p << ',' << f << ',' << sl << ','
                          << (q == requested ? "filled" : "cash_limited") << '\n';
            }
            double mv = 0;
            for (auto [s, q] : shares) {
                double o = marks.count(s) ? marks[s] : 0, c = o;
                if (bars.count(s)) {
                    o = bars[s].open;
                    c = bars[s].close;
                }
                in[s] = q * (c - o);
                intraday += in[s];
                marks[s] = c;
                mv += q * c;
                pos << date << ',' << s << ',' << q << ',' << c << ',' << q * c << '\n';
                if (q < 0)
                    throw runtime_error("negative shares");
            }
            double equity = cash + mv,
                   residual = (equity - prev) - (overnight + intraday - fees - slippage);
            if (cash < -1e-7 || abs(residual) > 1e-6 * max(1., equity / 100000))
                throw runtime_error("reconciliation failure");
            eq << date << ',' << equity << ',' << cash << ',' << mv / equity << ',' << overnight
               << ',' << intraday << ',' << fees << ',' << slippage << ',' << traded / prev << ','
               << residual << ',' << stale << '\n';
            for (auto [s, q] : shares)
                attr << date << ',' << s << ',' << ov[s] << ',' << in[s] << ',' << fc[s] << ','
                     << sc[s] << ',' << ov[s] + in[s] - fc[s] - sc[s] << '\n';
            prev = equity;
            signals.erase(open);
        }
        for (auto [t, ss] : signals)
            for (auto s : ss)
                fills << t.substr(0, 10) << ',' << s.sym << ',' << s.time << ',' << t
                      << ",0,0,0,0,0,unavailable_session\n";
        return 0;
    } catch (exception &e) {
        cerr << e.what() << '\n';
        return 1;
    }
}
