// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtop.h for the primary calling header

#include "Vtop__pch.h"

VL_ATTR_COLD void Vtop___024root___eval_static(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___eval_static\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__Vtrigprevexpr___TOP__skid_buffer__DOT__clk__0 
        = vlSelfRef.skid_buffer__DOT__clk;
}

VL_ATTR_COLD void Vtop___024root___eval_initial(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___eval_initial\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

VL_ATTR_COLD void Vtop___024root___eval_final(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___eval_final\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtop___024root___dump_triggers__stl(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG
VL_ATTR_COLD bool Vtop___024root___eval_phase__stl(Vtop___024root* vlSelf);

VL_ATTR_COLD void Vtop___024root___eval_settle(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___eval_settle\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    IData/*31:0*/ __VstlIterCount;
    // Body
    __VstlIterCount = 0U;
    vlSelfRef.__VstlFirstIteration = 1U;
    do {
        if (VL_UNLIKELY(((0x00002710U < __VstlIterCount)))) {
#ifdef VL_DEBUG
            Vtop___024root___dump_triggers__stl(vlSelfRef.__VstlTriggered, "stl"s);
#endif
            VL_FATAL_MT("/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 8, "", "DIDNOTCONVERGE: Settle region did not converge after '--converge-limit' of 10000 tries");
        }
        __VstlIterCount = ((IData)(1U) + __VstlIterCount);
        vlSelfRef.__VstlPhaseResult = Vtop___024root___eval_phase__stl(vlSelf);
        vlSelfRef.__VstlFirstIteration = 0U;
    } while (vlSelfRef.__VstlPhaseResult);
}

VL_ATTR_COLD bool Vtop___024root___trigger_anySet__stl(const VlUnpacked<QData/*63:0*/, 1> &in);

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtop___024root___dump_triggers__stl(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___dump_triggers__stl\n"); );
    // Body
    if ((1U & (~ (IData)(Vtop___024root___trigger_anySet__stl(triggers))))) {
        VL_DBG_MSGS("         No '" + tag + "' region triggers active\n");
    }
    if ((1U & (IData)(triggers[0U]))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 0 is active: Internal 'stl' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD bool Vtop___024root___trigger_anySet__stl(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___trigger_anySet__stl\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        if (in[n]) {
            return (1U);
        }
        n = ((IData)(1U) + n);
    } while ((1U > n));
    return (0U);
}

void Vtop___024root___ico_sequent__TOP__0(Vtop___024root* vlSelf);

VL_ATTR_COLD bool Vtop___024root___eval_phase__stl(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___eval_phase__stl\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VstlExecute;
    // Body
    {
        // Inlined CFunc: _eval_triggers_vec__stl
        vlSelfRef.__VstlTriggered[0U] = ((0xfffffffffffffffeULL 
                                          & vlSelfRef.__VstlTriggered[0U]) 
                                         | (IData)((IData)(vlSelfRef.__VstlFirstIteration)));
    }
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtop___024root___dump_triggers__stl(vlSelfRef.__VstlTriggered, "stl"s);
    }
#endif
    __VstlExecute = Vtop___024root___trigger_anySet__stl(vlSelfRef.__VstlTriggered);
    if (__VstlExecute) {
        {
            // Inlined CFunc: _eval_stl
            if ((1ULL & vlSelfRef.__VstlTriggered[0U])) {
                Vtop___024root___ico_sequent__TOP__0(vlSelf);
            }
        }
    }
    return (__VstlExecute);
}

bool Vtop___024root___trigger_anySet__ico(const VlUnpacked<QData/*63:0*/, 1> &in);

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtop___024root___dump_triggers__ico(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___dump_triggers__ico\n"); );
    // Body
    if ((1U & (~ (IData)(Vtop___024root___trigger_anySet__ico(triggers))))) {
        VL_DBG_MSGS("         No '" + tag + "' region triggers active\n");
    }
    if ((1U & (IData)(triggers[0U]))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 0 is active: Internal 'ico' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

bool Vtop___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in);

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtop___024root___dump_triggers__act(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___dump_triggers__act\n"); );
    // Body
    if ((1U & (~ (IData)(Vtop___024root___trigger_anySet__act(triggers))))) {
        VL_DBG_MSGS("         No '" + tag + "' region triggers active\n");
    }
    if ((1U & (IData)(triggers[0U]))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 0 is active: @(posedge skid_buffer.clk)\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vtop___024root___ctor_var_reset(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___ctor_var_reset\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    const uint64_t __VscopeHash = VL_MURMUR64_HASH(vlSelf->vlNamep);
    vlSelf->clk = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 16707436170211756652ull);
    vlSelf->rst_n = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 1638864771569018232ull);
    vlSelf->in_valid = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 2339549897027650563ull);
    vlSelf->in_ready = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 1122049356863891575ull);
    vlSelf->in_data = VL_SCOPED_RAND_RESET_I(32, __VscopeHash, 4057622023130387117ull);
    vlSelf->out_valid = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 2886291494070200219ull);
    vlSelf->out_ready = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 17332470166291283643ull);
    vlSelf->out_data = VL_SCOPED_RAND_RESET_I(32, __VscopeHash, 10144880484820144978ull);
    vlSelf->skid_buffer__DOT__clk = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 333228075343735663ull);
    vlSelf->skid_buffer__DOT__rst_n = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 12679958722299809662ull);
    vlSelf->skid_buffer__DOT__in_valid = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 15827178980850657302ull);
    vlSelf->skid_buffer__DOT__in_ready = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 2983247060753088572ull);
    vlSelf->skid_buffer__DOT__in_data = VL_SCOPED_RAND_RESET_I(32, __VscopeHash, 13451345918974636865ull);
    vlSelf->skid_buffer__DOT__out_valid = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 5214533655799263919ull);
    vlSelf->skid_buffer__DOT__out_ready = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 9366832402448844779ull);
    vlSelf->skid_buffer__DOT__out_data = VL_SCOPED_RAND_RESET_I(32, __VscopeHash, 298150333019712063ull);
    vlSelf->skid_buffer__DOT__skid_valid = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 17688532644479875701ull);
    vlSelf->skid_buffer__DOT__skid_data = VL_SCOPED_RAND_RESET_I(32, __VscopeHash, 10675785715297787693ull);
    vlSelf->skid_buffer__DOT__skid_valid_next = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 4279307850135044136ull);
    vlSelf->skid_buffer__DOT__skid_data_next = VL_SCOPED_RAND_RESET_I(32, __VscopeHash, 904598770710487738ull);
    vlSelf->skid_buffer__DOT__out_valid_next = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 14763067298986883754ull);
    vlSelf->skid_buffer__DOT__out_data_next = VL_SCOPED_RAND_RESET_I(32, __VscopeHash, 17528335087108750589ull);
    vlSelf->skid_buffer__DOT__in_fire = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 4297003649067867352ull);
    vlSelf->skid_buffer__DOT__out_fire = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 11847261794522058407ull);
    vlSelf->skid_buffer__DOT____Vtogcov__clk = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__rst_n = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__in_valid = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__in_ready = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__in_data = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__out_valid = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__out_ready = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__out_data = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__skid_valid = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__skid_data = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__skid_valid_next = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__skid_data_next = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__out_valid_next = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__out_data_next = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__in_fire = 0;
    vlSelf->skid_buffer__DOT____Vtogcov__out_fire = 0;
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VstlTriggered[__Vi0] = 0;
    }
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VicoTriggered[__Vi0] = 0;
    }
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VactTriggered[__Vi0] = 0;
    }
    vlSelf->__Vtrigprevexpr___TOP__skid_buffer__DOT__clk__0 = 0;
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VnbaTriggered[__Vi0] = 0;
    }
}

VL_ATTR_COLD void Vtop___024root___configure_coverage(Vtop___024root* vlSelf, bool first) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___configure_coverage\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    (void)first;  // Prevent unused variable warning
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 0, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 11, 30, ".skid_buffer", "v_toggle/skid_buffer", "clk");
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 2, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 12, 30, ".skid_buffer", "v_toggle/skid_buffer", "rst_n");
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 4, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 13, 30, ".skid_buffer", "v_toggle/skid_buffer", "in_valid");
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 6, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 14, 30, ".skid_buffer", "v_toggle/skid_buffer", "in_ready");
    vlSelf->__vlCoverToggleInsert(0, 31, 1, vlSelf->__Vcoverage + 8, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 15, 30, ".skid_buffer", "v_toggle/skid_buffer", "in_data");
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 72, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 16, 30, ".skid_buffer", "v_toggle/skid_buffer", "out_valid");
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 74, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 17, 30, ".skid_buffer", "v_toggle/skid_buffer", "out_ready");
    vlSelf->__vlCoverToggleInsert(0, 31, 1, vlSelf->__Vcoverage + 76, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 18, 30, ".skid_buffer", "v_toggle/skid_buffer", "out_data");
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 140, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 21, 23, ".skid_buffer", "v_toggle/skid_buffer", "skid_valid");
    vlSelf->__vlCoverToggleInsert(0, 31, 1, vlSelf->__Vcoverage + 142, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 22, 23, ".skid_buffer", "v_toggle/skid_buffer", "skid_data");
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 206, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 23, 23, ".skid_buffer", "v_toggle/skid_buffer", "skid_valid_next");
    vlSelf->__vlCoverToggleInsert(0, 31, 1, vlSelf->__Vcoverage + 208, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 24, 23, ".skid_buffer", "v_toggle/skid_buffer", "skid_data_next");
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 272, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 25, 23, ".skid_buffer", "v_toggle/skid_buffer", "out_valid_next");
    vlSelf->__vlCoverToggleInsert(0, 31, 1, vlSelf->__Vcoverage + 274, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 26, 23, ".skid_buffer", "v_toggle/skid_buffer", "out_data_next");
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 338, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 27, 23, ".skid_buffer", "v_toggle/skid_buffer", "in_fire");
    vlSelf->__vlCoverToggleInsert(0, 0, 0, vlSelf->__Vcoverage + 340, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 28, 23, ".skid_buffer", "v_toggle/skid_buffer", "out_fire");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 342, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 31, 23, ".skid_buffer", "v_expr/skid_buffer", "(skid_valid==0) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 342, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 31, 23, ".skid_buffer", "v_expr/skid_buffer", "(skid_valid==0) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 343, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 31, 23, ".skid_buffer", "v_expr/skid_buffer", "(skid_valid==1) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 343, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 31, 23, ".skid_buffer", "v_expr/skid_buffer", "(skid_valid==1) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 344, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 34, 36, ".skid_buffer", "v_expr/skid_buffer", "(in_valid==1 && in_ready==1) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 344, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 34, 36, ".skid_buffer", "v_expr/skid_buffer", "(in_valid==1 && in_ready==1) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 345, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 34, 36, ".skid_buffer", "v_expr/skid_buffer", "(in_ready==0) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 345, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 34, 36, ".skid_buffer", "v_expr/skid_buffer", "(in_ready==0) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 346, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 34, 36, ".skid_buffer", "v_expr/skid_buffer", "(in_valid==0) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 346, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 34, 36, ".skid_buffer", "v_expr/skid_buffer", "(in_valid==0) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 347, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 35, 37, ".skid_buffer", "v_expr/skid_buffer", "(out_valid==1 && out_ready==1) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 347, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 35, 37, ".skid_buffer", "v_expr/skid_buffer", "(out_valid==1 && out_ready==1) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 348, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 35, 37, ".skid_buffer", "v_expr/skid_buffer", "(out_ready==0) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 348, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 35, 37, ".skid_buffer", "v_expr/skid_buffer", "(out_ready==0) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 349, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 35, 37, ".skid_buffer", "v_expr/skid_buffer", "(out_valid==0) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 349, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 35, 37, ".skid_buffer", "v_expr/skid_buffer", "(out_valid==0) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 350, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 43, 13, ".skid_buffer", "v_branch/skid_buffer", "if", "43-46", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 350, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 43, 13, ".skid_buffer", "v_branch/skid_buffer", "if", "43-46", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 351, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 43, 14, ".skid_buffer", "v_branch/skid_buffer", "else", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 351, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 43, 14, ".skid_buffer", "v_branch/skid_buffer", "else", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 352, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 52, 34, ".skid_buffer", "v_expr/skid_buffer", "(in_fire==1) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 352, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 52, 34, ".skid_buffer", "v_expr/skid_buffer", "(in_fire==1) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 353, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 52, 34, ".skid_buffer", "v_expr/skid_buffer", "(in_fire==0) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 353, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 52, 34, ".skid_buffer", "v_expr/skid_buffer", "(in_fire==0) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 354, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 52, 44, ".skid_buffer", "v_branch/skid_buffer", "cond_then", "52", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 354, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 52, 44, ".skid_buffer", "v_branch/skid_buffer", "cond_then", "52", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 355, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 52, 45, ".skid_buffer", "v_branch/skid_buffer", "cond_else", "52", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 355, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 52, 45, ".skid_buffer", "v_branch/skid_buffer", "cond_else", "52", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 356, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 53, 22, ".skid_buffer", "v_branch/skid_buffer", "if", "53,55-56", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 356, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 53, 22, ".skid_buffer", "v_branch/skid_buffer", "if", "53,55-56", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 357, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 53, 23, ".skid_buffer", "v_branch/skid_buffer", "else", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 357, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 53, 23, ".skid_buffer", "v_branch/skid_buffer", "else", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 358, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 49, 13, ".skid_buffer", "v_line/skid_buffer", "elsif", "49,51-52", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 358, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 49, 13, ".skid_buffer", "v_line/skid_buffer", "elsif", "49,51-52", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 359, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 49, 26, ".skid_buffer", "v_expr/skid_buffer", "(out_valid==0) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 359, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 49, 26, ".skid_buffer", "v_expr/skid_buffer", "(out_valid==0) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 360, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 49, 26, ".skid_buffer", "v_expr/skid_buffer", "(out_fire==1) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 360, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 49, 26, ".skid_buffer", "v_expr/skid_buffer", "(out_fire==1) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 361, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 49, 26, ".skid_buffer", "v_expr/skid_buffer", "(out_fire==0 && out_valid==1) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 361, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 49, 26, ".skid_buffer", "v_expr/skid_buffer", "(out_fire==0 && out_valid==1) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 362, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 41, 9, ".skid_buffer", "v_branch/skid_buffer", "if", "41", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 362, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 41, 9, ".skid_buffer", "v_branch/skid_buffer", "if", "41", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 363, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 41, 10, ".skid_buffer", "v_branch/skid_buffer", "else", "48", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 363, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 41, 10, ".skid_buffer", "v_branch/skid_buffer", "else", "48", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 364, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 33, 5, ".skid_buffer", "v_line/skid_buffer", "block", "33-39", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 364, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 33, 5, ".skid_buffer", "v_line/skid_buffer", "block", "33-39", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 365, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 62, 9, ".skid_buffer", "v_branch/skid_buffer", "if", "62-64", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 365, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 62, 9, ".skid_buffer", "v_branch/skid_buffer", "if", "62-64", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 366, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 62, 10, ".skid_buffer", "v_branch/skid_buffer", "else", "65-67", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 366, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 62, 10, ".skid_buffer", "v_branch/skid_buffer", "else", "65-67", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 367, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 62, 13, ".skid_buffer", "v_expr/skid_buffer", "(rst_n==0) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 367, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 62, 13, ".skid_buffer", "v_expr/skid_buffer", "(rst_n==0) => 1", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 368, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 62, 13, ".skid_buffer", "v_expr/skid_buffer", "(rst_n==1) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 368, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 62, 13, ".skid_buffer", "v_expr/skid_buffer", "(rst_n==1) => 0", "", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 369, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 61, 5, ".skid_buffer", "v_line/skid_buffer", "block", "61", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 369, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 61, 5, ".skid_buffer", "v_line/skid_buffer", "block", "61", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSelf->__Vcoverage + 370, first, true, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 71, 5, ".skid_buffer", "v_line/skid_buffer", "block", "71-73", "", "", "", "");
    vlSelf->__vlCoverInsert(vlSymsp->__Vcoverage + 370, first, false, "/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 71, 5, ".skid_buffer", "v_line/skid_buffer", "block", "71-73", "", "", "", "");
}
