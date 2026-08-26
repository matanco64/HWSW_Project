// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtop.h for the primary calling header

#ifndef VERILATED_VTOP___024ROOT_H_
#define VERILATED_VTOP___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_cov.h"
#include "verilated_covergroup.h"


class Vtop__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtop___024root final {
  public:

    // DESIGN SPECIFIC STATE
    VL_IN8(clk,0,0);
    VL_IN8(rst_n,0,0);
    VL_IN8(in_valid,0,0);
    VL_OUT8(in_ready,0,0);
    VL_OUT8(out_valid,0,0);
    VL_IN8(out_ready,0,0);
    CData/*0:0*/ skid_buffer__DOT__clk;
    CData/*0:0*/ skid_buffer__DOT__rst_n;
    CData/*0:0*/ skid_buffer__DOT__in_valid;
    CData/*0:0*/ skid_buffer__DOT__in_ready;
    CData/*0:0*/ skid_buffer__DOT__out_valid;
    CData/*0:0*/ skid_buffer__DOT__out_ready;
    CData/*0:0*/ skid_buffer__DOT__skid_valid;
    CData/*0:0*/ skid_buffer__DOT__skid_valid_next;
    CData/*0:0*/ skid_buffer__DOT__out_valid_next;
    CData/*0:0*/ skid_buffer__DOT__in_fire;
    CData/*0:0*/ skid_buffer__DOT__out_fire;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__clk;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__rst_n;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__in_valid;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__in_ready;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__out_valid;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__out_ready;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__skid_valid;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__skid_valid_next;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__out_valid_next;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__in_fire;
    CData/*0:0*/ skid_buffer__DOT____Vtogcov__out_fire;
    CData/*0:0*/ __VstlFirstIteration;
    CData/*0:0*/ __VstlPhaseResult;
    CData/*0:0*/ __VicoFirstIteration;
    CData/*0:0*/ __VicoPhaseResult;
    CData/*0:0*/ __Vtrigprevexpr___TOP__skid_buffer__DOT__clk__0;
    CData/*0:0*/ __VactPhaseResult;
    CData/*0:0*/ __VnbaPhaseResult;
    VL_IN(in_data,31,0);
    VL_OUT(out_data,31,0);
    IData/*31:0*/ skid_buffer__DOT____VlemCond_0;
    IData/*31:0*/ skid_buffer__DOT__in_data;
    IData/*31:0*/ skid_buffer__DOT__out_data;
    IData/*31:0*/ skid_buffer__DOT__skid_data;
    IData/*31:0*/ skid_buffer__DOT__skid_data_next;
    IData/*31:0*/ skid_buffer__DOT__out_data_next;
    IData/*31:0*/ skid_buffer__DOT____Vtogcov__in_data;
    IData/*31:0*/ skid_buffer__DOT____Vtogcov__out_data;
    IData/*31:0*/ skid_buffer__DOT____Vtogcov__skid_data;
    IData/*31:0*/ skid_buffer__DOT____Vtogcov__skid_data_next;
    IData/*31:0*/ skid_buffer__DOT____Vtogcov__out_data_next;
    IData/*31:0*/ __VactIterCount;
    VlUnpacked<QData/*63:0*/, 1> __VstlTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VicoTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VactTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vtop__Syms* vlSymsp;
    const char* vlNamep;
    uint32_t __Vcoverage[371]{};

    // PARAMETERS
    static constexpr IData/*31:0*/ skid_buffer__DOT__WIDTH = 0x00000020U;

    // CONSTRUCTORS
    Vtop___024root(Vtop__Syms* symsp, const char* namep);
    ~Vtop___024root();
    VL_UNCOPYABLE(Vtop___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
    void __vlCoverInsert(uint32_t* countp, bool enable, bool localCounter, const char* filenamep, int lineno, int column,
        const char* hierp, const char* pagep, const char* commentp, const char* linescovp,
        const char* fsmVarp, const char* fsmFromp, const char* fsmTop, const char* fsmTagp);
    void __vlCoverToggleInsert(int begin, int end, bool ranged, uint32_t* countp, bool enable, bool localCounter, const char* filenamep, int lineno, int column,
        const char* hierp, const char* pagep, const char* commentp);
};


#endif  // guard
