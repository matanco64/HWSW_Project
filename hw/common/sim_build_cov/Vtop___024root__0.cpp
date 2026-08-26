// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtop.h for the primary calling header

#include "Vtop__pch.h"

bool Vtop___024root___trigger_anySet__ico(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___trigger_anySet__ico\n"); );
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

void Vtop___024root___ico_sequent__TOP__0(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___ico_sequent__TOP__0\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__skid_valid)))) {
        ++(vlSelf->__Vcoverage[342]);
    }
    if (vlSelfRef.skid_buffer__DOT__skid_valid) {
        ++(vlSelf->__Vcoverage[343]);
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__out_valid) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 72, vlSelfRef.skid_buffer__DOT__out_valid, vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid 
            = vlSelfRef.skid_buffer__DOT__out_valid;
    }
    if ((0U != (vlSelfRef.skid_buffer__DOT__out_data 
                ^ vlSelfRef.skid_buffer__DOT____Vtogcov__out_data))) {
        VL_COV_TOGGLE_CHG_ST_I(32, vlSelf->__Vcoverage + 76, vlSelfRef.skid_buffer__DOT__out_data, vlSelfRef.skid_buffer__DOT____Vtogcov__out_data);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_data 
            = vlSelfRef.skid_buffer__DOT__out_data;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__skid_valid) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 140, vlSelfRef.skid_buffer__DOT__skid_valid, vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid);
        vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid 
            = vlSelfRef.skid_buffer__DOT__skid_valid;
    }
    if ((0U != (vlSelfRef.skid_buffer__DOT__skid_data 
                ^ vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data))) {
        VL_COV_TOGGLE_CHG_ST_I(32, vlSelf->__Vcoverage + 142, vlSelfRef.skid_buffer__DOT__skid_data, vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data);
        vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data 
            = vlSelfRef.skid_buffer__DOT__skid_data;
    }
    vlSelfRef.out_valid = vlSelfRef.skid_buffer__DOT__out_valid;
    vlSelfRef.out_data = vlSelfRef.skid_buffer__DOT__out_data;
    vlSelfRef.skid_buffer__DOT__clk = vlSelfRef.clk;
    vlSelfRef.skid_buffer__DOT__rst_n = vlSelfRef.rst_n;
    vlSelfRef.skid_buffer__DOT__in_valid = vlSelfRef.in_valid;
    vlSelfRef.skid_buffer__DOT__in_data = vlSelfRef.in_data;
    vlSelfRef.skid_buffer__DOT__out_ready = vlSelfRef.out_ready;
    vlSelfRef.skid_buffer__DOT__in_ready = (1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__skid_valid)));
    if (((IData)(vlSelfRef.skid_buffer__DOT__clk) ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__clk))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 0, vlSelfRef.skid_buffer__DOT__clk, vlSelfRef.skid_buffer__DOT____Vtogcov__clk);
        vlSelfRef.skid_buffer__DOT____Vtogcov__clk 
            = vlSelfRef.skid_buffer__DOT__clk;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__rst_n) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__rst_n))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 2, vlSelfRef.skid_buffer__DOT__rst_n, vlSelfRef.skid_buffer__DOT____Vtogcov__rst_n);
        vlSelfRef.skid_buffer__DOT____Vtogcov__rst_n 
            = vlSelfRef.skid_buffer__DOT__rst_n;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__in_valid) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__in_valid))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 4, vlSelfRef.skid_buffer__DOT__in_valid, vlSelfRef.skid_buffer__DOT____Vtogcov__in_valid);
        vlSelfRef.skid_buffer__DOT____Vtogcov__in_valid 
            = vlSelfRef.skid_buffer__DOT__in_valid;
    }
    if ((0U != (vlSelfRef.skid_buffer__DOT__in_data 
                ^ vlSelfRef.skid_buffer__DOT____Vtogcov__in_data))) {
        VL_COV_TOGGLE_CHG_ST_I(32, vlSelf->__Vcoverage + 8, vlSelfRef.skid_buffer__DOT__in_data, vlSelfRef.skid_buffer__DOT____Vtogcov__in_data);
        vlSelfRef.skid_buffer__DOT____Vtogcov__in_data 
            = vlSelfRef.skid_buffer__DOT__in_data;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__out_ready) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__out_ready))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 74, vlSelfRef.skid_buffer__DOT__out_ready, vlSelfRef.skid_buffer__DOT____Vtogcov__out_ready);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_ready 
            = vlSelfRef.skid_buffer__DOT__out_ready;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__in_ready) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__in_ready))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 6, vlSelfRef.skid_buffer__DOT__in_ready, vlSelfRef.skid_buffer__DOT____Vtogcov__in_ready);
        vlSelfRef.skid_buffer__DOT____Vtogcov__in_ready 
            = vlSelfRef.skid_buffer__DOT__in_ready;
    }
    vlSelfRef.in_ready = vlSelfRef.skid_buffer__DOT__in_ready;
    vlSelfRef.skid_buffer__DOT__in_fire = ((IData)(vlSelfRef.skid_buffer__DOT__in_valid) 
                                           & (IData)(vlSelfRef.skid_buffer__DOT__in_ready));
    vlSelfRef.skid_buffer__DOT__out_fire = ((IData)(vlSelfRef.skid_buffer__DOT__out_valid) 
                                            & (IData)(vlSelfRef.skid_buffer__DOT__out_ready));
    vlSelfRef.skid_buffer__DOT__skid_valid_next = vlSelfRef.skid_buffer__DOT__skid_valid;
    vlSelfRef.skid_buffer__DOT__skid_data_next = vlSelfRef.skid_buffer__DOT__skid_data;
    vlSelfRef.skid_buffer__DOT__out_valid_next = vlSelfRef.skid_buffer__DOT__out_valid;
    vlSelfRef.skid_buffer__DOT__out_data_next = vlSelfRef.skid_buffer__DOT__out_data;
    if (vlSelfRef.skid_buffer__DOT__skid_valid) {
        if (vlSelfRef.skid_buffer__DOT__out_fire) {
            vlSelfRef.skid_buffer__DOT__out_valid_next = 1U;
            vlSelfRef.skid_buffer__DOT__out_data_next 
                = vlSelfRef.skid_buffer__DOT__skid_data;
            vlSelfRef.skid_buffer__DOT__skid_valid_next = 0U;
            ++(vlSelf->__Vcoverage[350]);
        } else {
            ++(vlSelf->__Vcoverage[351]);
        }
        ++(vlSelf->__Vcoverage[362]);
    } else {
        if ((1U & ((IData)(vlSelfRef.skid_buffer__DOT__out_fire) 
                   | (~ (IData)(vlSelfRef.skid_buffer__DOT__out_valid))))) {
            vlSelfRef.skid_buffer__DOT__out_valid_next 
                = vlSelfRef.skid_buffer__DOT__in_fire;
            if (vlSelfRef.skid_buffer__DOT__in_fire) {
                ++(vlSelf->__Vcoverage[354]);
                vlSelfRef.skid_buffer__DOT____VlemCond_0 
                    = vlSelfRef.skid_buffer__DOT__in_data;
            } else {
                ++(vlSelf->__Vcoverage[355]);
                vlSelfRef.skid_buffer__DOT____VlemCond_0 
                    = vlSelfRef.skid_buffer__DOT__out_data;
            }
            vlSelfRef.skid_buffer__DOT__out_data_next 
                = vlSelfRef.skid_buffer__DOT____VlemCond_0;
            if (vlSelfRef.skid_buffer__DOT__in_fire) {
                ++(vlSelf->__Vcoverage[352]);
            }
            if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__in_fire)))) {
                ++(vlSelf->__Vcoverage[353]);
            }
            ++(vlSelf->__Vcoverage[358]);
        } else if (vlSelfRef.skid_buffer__DOT__in_fire) {
            vlSelfRef.skid_buffer__DOT__skid_valid_next = 1U;
            vlSelfRef.skid_buffer__DOT__skid_data_next 
                = vlSelfRef.skid_buffer__DOT__in_data;
            ++(vlSelf->__Vcoverage[356]);
        } else {
            ++(vlSelf->__Vcoverage[357]);
        }
        if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__out_valid)))) {
            ++(vlSelf->__Vcoverage[359]);
        }
        if (vlSelfRef.skid_buffer__DOT__out_fire) {
            ++(vlSelf->__Vcoverage[360]);
        }
        if (((~ (IData)(vlSelfRef.skid_buffer__DOT__out_fire)) 
             & (IData)(vlSelfRef.skid_buffer__DOT__out_valid))) {
            ++(vlSelf->__Vcoverage[361]);
        }
        ++(vlSelf->__Vcoverage[363]);
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__in_valid) 
         & (IData)(vlSelfRef.skid_buffer__DOT__in_ready))) {
        ++(vlSelf->__Vcoverage[344]);
    }
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__in_ready)))) {
        ++(vlSelf->__Vcoverage[345]);
    }
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__in_valid)))) {
        ++(vlSelf->__Vcoverage[346]);
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__out_valid) 
         & (IData)(vlSelfRef.skid_buffer__DOT__out_ready))) {
        ++(vlSelf->__Vcoverage[347]);
    }
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__out_ready)))) {
        ++(vlSelf->__Vcoverage[348]);
    }
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__out_valid)))) {
        ++(vlSelf->__Vcoverage[349]);
    }
    ++(vlSelf->__Vcoverage[364]);
    if (((IData)(vlSelfRef.skid_buffer__DOT__in_fire) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__in_fire))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 338, vlSelfRef.skid_buffer__DOT__in_fire, vlSelfRef.skid_buffer__DOT____Vtogcov__in_fire);
        vlSelfRef.skid_buffer__DOT____Vtogcov__in_fire 
            = vlSelfRef.skid_buffer__DOT__in_fire;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__out_fire) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__out_fire))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 340, vlSelfRef.skid_buffer__DOT__out_fire, vlSelfRef.skid_buffer__DOT____Vtogcov__out_fire);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_fire 
            = vlSelfRef.skid_buffer__DOT__out_fire;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__skid_valid_next) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid_next))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 206, vlSelfRef.skid_buffer__DOT__skid_valid_next, vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid_next);
        vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid_next 
            = vlSelfRef.skid_buffer__DOT__skid_valid_next;
    }
    if ((0U != (vlSelfRef.skid_buffer__DOT__skid_data_next 
                ^ vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data_next))) {
        VL_COV_TOGGLE_CHG_ST_I(32, vlSelf->__Vcoverage + 208, vlSelfRef.skid_buffer__DOT__skid_data_next, vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data_next);
        vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data_next 
            = vlSelfRef.skid_buffer__DOT__skid_data_next;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__out_valid_next) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid_next))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 272, vlSelfRef.skid_buffer__DOT__out_valid_next, vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid_next);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid_next 
            = vlSelfRef.skid_buffer__DOT__out_valid_next;
    }
    if ((0U != (vlSelfRef.skid_buffer__DOT__out_data_next 
                ^ vlSelfRef.skid_buffer__DOT____Vtogcov__out_data_next))) {
        VL_COV_TOGGLE_CHG_ST_I(32, vlSelf->__Vcoverage + 274, vlSelfRef.skid_buffer__DOT__out_data_next, vlSelfRef.skid_buffer__DOT____Vtogcov__out_data_next);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_data_next 
            = vlSelfRef.skid_buffer__DOT__out_data_next;
    }
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtop___024root___dump_triggers__ico(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG

bool Vtop___024root___eval_phase__ico(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___eval_phase__ico\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VicoExecute;
    // Body
    {
        // Inlined CFunc: _eval_triggers_vec__ico
        vlSelfRef.__VicoTriggered[0U] = ((0xfffffffffffffffeULL 
                                          & vlSelfRef.__VicoTriggered[0U]) 
                                         | (IData)((IData)(vlSelfRef.__VicoFirstIteration)));
    }
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtop___024root___dump_triggers__ico(vlSelfRef.__VicoTriggered, "ico"s);
    }
#endif
    __VicoExecute = Vtop___024root___trigger_anySet__ico(vlSelfRef.__VicoTriggered);
    if (__VicoExecute) {
        {
            // Inlined CFunc: _eval_ico
            if ((1ULL & vlSelfRef.__VicoTriggered[0U])) {
                Vtop___024root___ico_sequent__TOP__0(vlSelf);
            }
        }
    }
    return (__VicoExecute);
}

bool Vtop___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___trigger_anySet__act\n"); );
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

void Vtop___024root___nba_sequent__TOP__0(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___nba_sequent__TOP__0\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    ++(vlSelf->__Vcoverage[370]);
    vlSelfRef.skid_buffer__DOT__skid_data = vlSelfRef.skid_buffer__DOT__skid_data_next;
    vlSelfRef.skid_buffer__DOT__out_data = vlSelfRef.skid_buffer__DOT__out_data_next;
    if (vlSelfRef.skid_buffer__DOT__rst_n) {
        ++(vlSelf->__Vcoverage[366]);
        vlSelfRef.skid_buffer__DOT__skid_valid = vlSelfRef.skid_buffer__DOT__skid_valid_next;
        vlSelfRef.skid_buffer__DOT__out_valid = vlSelfRef.skid_buffer__DOT__out_valid_next;
    } else {
        ++(vlSelf->__Vcoverage[365]);
        vlSelfRef.skid_buffer__DOT__skid_valid = 0U;
        vlSelfRef.skid_buffer__DOT__out_valid = 0U;
    }
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__rst_n)))) {
        ++(vlSelf->__Vcoverage[367]);
    }
    if (vlSelfRef.skid_buffer__DOT__rst_n) {
        ++(vlSelf->__Vcoverage[368]);
    }
    ++(vlSelf->__Vcoverage[369]);
    if ((0U != (vlSelfRef.skid_buffer__DOT__skid_data 
                ^ vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data))) {
        VL_COV_TOGGLE_CHG_ST_I(32, vlSelf->__Vcoverage + 142, vlSelfRef.skid_buffer__DOT__skid_data, vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data);
        vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data 
            = vlSelfRef.skid_buffer__DOT__skid_data;
    }
    if ((0U != (vlSelfRef.skid_buffer__DOT__out_data 
                ^ vlSelfRef.skid_buffer__DOT____Vtogcov__out_data))) {
        VL_COV_TOGGLE_CHG_ST_I(32, vlSelf->__Vcoverage + 76, vlSelfRef.skid_buffer__DOT__out_data, vlSelfRef.skid_buffer__DOT____Vtogcov__out_data);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_data 
            = vlSelfRef.skid_buffer__DOT__out_data;
    }
    vlSelfRef.out_data = vlSelfRef.skid_buffer__DOT__out_data;
    if (((IData)(vlSelfRef.skid_buffer__DOT__out_valid) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 72, vlSelfRef.skid_buffer__DOT__out_valid, vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid 
            = vlSelfRef.skid_buffer__DOT__out_valid;
    }
    vlSelfRef.out_valid = vlSelfRef.skid_buffer__DOT__out_valid;
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__skid_valid)))) {
        ++(vlSelf->__Vcoverage[342]);
    }
    if (vlSelfRef.skid_buffer__DOT__skid_valid) {
        ++(vlSelf->__Vcoverage[343]);
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__skid_valid) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 140, vlSelfRef.skid_buffer__DOT__skid_valid, vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid);
        vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid 
            = vlSelfRef.skid_buffer__DOT__skid_valid;
    }
    vlSelfRef.skid_buffer__DOT__in_ready = (1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__skid_valid)));
    if (((IData)(vlSelfRef.skid_buffer__DOT__in_ready) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__in_ready))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 6, vlSelfRef.skid_buffer__DOT__in_ready, vlSelfRef.skid_buffer__DOT____Vtogcov__in_ready);
        vlSelfRef.skid_buffer__DOT____Vtogcov__in_ready 
            = vlSelfRef.skid_buffer__DOT__in_ready;
    }
    vlSelfRef.in_ready = vlSelfRef.skid_buffer__DOT__in_ready;
    vlSelfRef.skid_buffer__DOT__in_fire = ((IData)(vlSelfRef.skid_buffer__DOT__in_valid) 
                                           & (IData)(vlSelfRef.skid_buffer__DOT__in_ready));
    vlSelfRef.skid_buffer__DOT__out_fire = ((IData)(vlSelfRef.skid_buffer__DOT__out_valid) 
                                            & (IData)(vlSelfRef.skid_buffer__DOT__out_ready));
    vlSelfRef.skid_buffer__DOT__skid_valid_next = vlSelfRef.skid_buffer__DOT__skid_valid;
    vlSelfRef.skid_buffer__DOT__skid_data_next = vlSelfRef.skid_buffer__DOT__skid_data;
    vlSelfRef.skid_buffer__DOT__out_valid_next = vlSelfRef.skid_buffer__DOT__out_valid;
    vlSelfRef.skid_buffer__DOT__out_data_next = vlSelfRef.skid_buffer__DOT__out_data;
    if (vlSelfRef.skid_buffer__DOT__skid_valid) {
        if (vlSelfRef.skid_buffer__DOT__out_fire) {
            vlSelfRef.skid_buffer__DOT__out_valid_next = 1U;
            vlSelfRef.skid_buffer__DOT__out_data_next 
                = vlSelfRef.skid_buffer__DOT__skid_data;
            vlSelfRef.skid_buffer__DOT__skid_valid_next = 0U;
            ++(vlSelf->__Vcoverage[350]);
        } else {
            ++(vlSelf->__Vcoverage[351]);
        }
        ++(vlSelf->__Vcoverage[362]);
    } else {
        if ((1U & ((IData)(vlSelfRef.skid_buffer__DOT__out_fire) 
                   | (~ (IData)(vlSelfRef.skid_buffer__DOT__out_valid))))) {
            vlSelfRef.skid_buffer__DOT__out_valid_next 
                = vlSelfRef.skid_buffer__DOT__in_fire;
            if (vlSelfRef.skid_buffer__DOT__in_fire) {
                ++(vlSelf->__Vcoverage[354]);
                vlSelfRef.skid_buffer__DOT____VlemCond_0 
                    = vlSelfRef.skid_buffer__DOT__in_data;
            } else {
                ++(vlSelf->__Vcoverage[355]);
                vlSelfRef.skid_buffer__DOT____VlemCond_0 
                    = vlSelfRef.skid_buffer__DOT__out_data;
            }
            vlSelfRef.skid_buffer__DOT__out_data_next 
                = vlSelfRef.skid_buffer__DOT____VlemCond_0;
            if (vlSelfRef.skid_buffer__DOT__in_fire) {
                ++(vlSelf->__Vcoverage[352]);
            }
            if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__in_fire)))) {
                ++(vlSelf->__Vcoverage[353]);
            }
            ++(vlSelf->__Vcoverage[358]);
        } else if (vlSelfRef.skid_buffer__DOT__in_fire) {
            vlSelfRef.skid_buffer__DOT__skid_valid_next = 1U;
            vlSelfRef.skid_buffer__DOT__skid_data_next 
                = vlSelfRef.skid_buffer__DOT__in_data;
            ++(vlSelf->__Vcoverage[356]);
        } else {
            ++(vlSelf->__Vcoverage[357]);
        }
        if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__out_valid)))) {
            ++(vlSelf->__Vcoverage[359]);
        }
        if (vlSelfRef.skid_buffer__DOT__out_fire) {
            ++(vlSelf->__Vcoverage[360]);
        }
        if (((~ (IData)(vlSelfRef.skid_buffer__DOT__out_fire)) 
             & (IData)(vlSelfRef.skid_buffer__DOT__out_valid))) {
            ++(vlSelf->__Vcoverage[361]);
        }
        ++(vlSelf->__Vcoverage[363]);
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__in_valid) 
         & (IData)(vlSelfRef.skid_buffer__DOT__in_ready))) {
        ++(vlSelf->__Vcoverage[344]);
    }
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__in_ready)))) {
        ++(vlSelf->__Vcoverage[345]);
    }
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__in_valid)))) {
        ++(vlSelf->__Vcoverage[346]);
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__out_valid) 
         & (IData)(vlSelfRef.skid_buffer__DOT__out_ready))) {
        ++(vlSelf->__Vcoverage[347]);
    }
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__out_ready)))) {
        ++(vlSelf->__Vcoverage[348]);
    }
    if ((1U & (~ (IData)(vlSelfRef.skid_buffer__DOT__out_valid)))) {
        ++(vlSelf->__Vcoverage[349]);
    }
    ++(vlSelf->__Vcoverage[364]);
    if (((IData)(vlSelfRef.skid_buffer__DOT__in_fire) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__in_fire))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 338, vlSelfRef.skid_buffer__DOT__in_fire, vlSelfRef.skid_buffer__DOT____Vtogcov__in_fire);
        vlSelfRef.skid_buffer__DOT____Vtogcov__in_fire 
            = vlSelfRef.skid_buffer__DOT__in_fire;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__out_fire) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__out_fire))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 340, vlSelfRef.skid_buffer__DOT__out_fire, vlSelfRef.skid_buffer__DOT____Vtogcov__out_fire);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_fire 
            = vlSelfRef.skid_buffer__DOT__out_fire;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__skid_valid_next) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid_next))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 206, vlSelfRef.skid_buffer__DOT__skid_valid_next, vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid_next);
        vlSelfRef.skid_buffer__DOT____Vtogcov__skid_valid_next 
            = vlSelfRef.skid_buffer__DOT__skid_valid_next;
    }
    if ((0U != (vlSelfRef.skid_buffer__DOT__skid_data_next 
                ^ vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data_next))) {
        VL_COV_TOGGLE_CHG_ST_I(32, vlSelf->__Vcoverage + 208, vlSelfRef.skid_buffer__DOT__skid_data_next, vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data_next);
        vlSelfRef.skid_buffer__DOT____Vtogcov__skid_data_next 
            = vlSelfRef.skid_buffer__DOT__skid_data_next;
    }
    if (((IData)(vlSelfRef.skid_buffer__DOT__out_valid_next) 
         ^ (IData)(vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid_next))) {
        VL_COV_TOGGLE_CHG_ST_I(1, vlSelf->__Vcoverage + 272, vlSelfRef.skid_buffer__DOT__out_valid_next, vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid_next);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_valid_next 
            = vlSelfRef.skid_buffer__DOT__out_valid_next;
    }
    if ((0U != (vlSelfRef.skid_buffer__DOT__out_data_next 
                ^ vlSelfRef.skid_buffer__DOT____Vtogcov__out_data_next))) {
        VL_COV_TOGGLE_CHG_ST_I(32, vlSelf->__Vcoverage + 274, vlSelfRef.skid_buffer__DOT__out_data_next, vlSelfRef.skid_buffer__DOT____Vtogcov__out_data_next);
        vlSelfRef.skid_buffer__DOT____Vtogcov__out_data_next 
            = vlSelfRef.skid_buffer__DOT__out_data_next;
    }
}

void Vtop___024root___trigger_orInto__act_vec_vec(VlUnpacked<QData/*63:0*/, 1> &out, const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___trigger_orInto__act_vec_vec\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        out[n] = (out[n] | in[n]);
        n = ((IData)(1U) + n);
    } while ((0U >= n));
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtop___024root___dump_triggers__act(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG

bool Vtop___024root___eval_phase__act(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___eval_phase__act\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    {
        // Inlined CFunc: _eval_triggers_vec__act
        vlSelfRef.__VactTriggered[0U] = (QData)((IData)(
                                                        ((IData)(vlSelfRef.skid_buffer__DOT__clk) 
                                                         & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__skid_buffer__DOT__clk__0)))));
        vlSelfRef.__Vtrigprevexpr___TOP__skid_buffer__DOT__clk__0 
            = vlSelfRef.skid_buffer__DOT__clk;
    }
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtop___024root___dump_triggers__act(vlSelfRef.__VactTriggered, "act"s);
    }
#endif
    Vtop___024root___trigger_orInto__act_vec_vec(vlSelfRef.__VnbaTriggered, vlSelfRef.__VactTriggered);
    return (0U);
}

void Vtop___024root___trigger_clear__act(VlUnpacked<QData/*63:0*/, 1> &out) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___trigger_clear__act\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        out[n] = 0ULL;
        n = ((IData)(1U) + n);
    } while ((1U > n));
}

bool Vtop___024root___eval_phase__nba(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___eval_phase__nba\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = Vtop___024root___trigger_anySet__act(vlSelfRef.__VnbaTriggered);
    if (__VnbaExecute) {
        {
            // Inlined CFunc: _eval_nba
            if ((1ULL & vlSelfRef.__VnbaTriggered[0U])) {
                Vtop___024root___nba_sequent__TOP__0(vlSelf);
            }
        }
        Vtop___024root___trigger_clear__act(vlSelfRef.__VnbaTriggered);
    }
    return (__VnbaExecute);
}

void Vtop___024root___eval(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___eval\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    IData/*31:0*/ __VicoIterCount;
    IData/*31:0*/ __VnbaIterCount;
    // Body
    __VicoIterCount = 0U;
    vlSelfRef.__VicoFirstIteration = 1U;
    do {
        if (VL_UNLIKELY(((0x00002710U < __VicoIterCount)))) {
#ifdef VL_DEBUG
            Vtop___024root___dump_triggers__ico(vlSelfRef.__VicoTriggered, "ico"s);
#endif
            VL_FATAL_MT("/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 8, "", "DIDNOTCONVERGE: Input combinational region did not converge after '--converge-limit' of 10000 tries");
        }
        __VicoIterCount = ((IData)(1U) + __VicoIterCount);
        vlSelfRef.__VicoPhaseResult = Vtop___024root___eval_phase__ico(vlSelf);
        vlSelfRef.__VicoFirstIteration = 0U;
    } while (vlSelfRef.__VicoPhaseResult);
    __VnbaIterCount = 0U;
    do {
        if (VL_UNLIKELY(((0x00002710U < __VnbaIterCount)))) {
#ifdef VL_DEBUG
            Vtop___024root___dump_triggers__act(vlSelfRef.__VnbaTriggered, "nba"s);
#endif
            VL_FATAL_MT("/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 8, "", "DIDNOTCONVERGE: NBA region did not converge after '--converge-limit' of 10000 tries");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        vlSelfRef.__VactIterCount = 0U;
        do {
            if (VL_UNLIKELY(((0x00002710U < vlSelfRef.__VactIterCount)))) {
#ifdef VL_DEBUG
                Vtop___024root___dump_triggers__act(vlSelfRef.__VactTriggered, "act"s);
#endif
                VL_FATAL_MT("/home/yuvalk/HWSW/HWSW_Proj/hw/common/rtl/skid_buffer.sv", 8, "", "DIDNOTCONVERGE: Active region did not converge after '--converge-limit' of 10000 tries");
            }
            vlSelfRef.__VactIterCount = ((IData)(1U) 
                                         + vlSelfRef.__VactIterCount);
            vlSelfRef.__VactPhaseResult = Vtop___024root___eval_phase__act(vlSelf);
        } while (vlSelfRef.__VactPhaseResult);
        vlSelfRef.__VnbaPhaseResult = Vtop___024root___eval_phase__nba(vlSelf);
    } while (vlSelfRef.__VnbaPhaseResult);
}

#ifdef VL_DEBUG
void Vtop___024root___eval_debug_assertions(Vtop___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root___eval_debug_assertions\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (VL_UNLIKELY(((vlSelfRef.clk & 0xfeU)))) {
        Verilated::overWidthError("clk");
    }
    if (VL_UNLIKELY(((vlSelfRef.rst_n & 0xfeU)))) {
        Verilated::overWidthError("rst_n");
    }
    if (VL_UNLIKELY(((vlSelfRef.in_valid & 0xfeU)))) {
        Verilated::overWidthError("in_valid");
    }
    if (VL_UNLIKELY(((vlSelfRef.out_ready & 0xfeU)))) {
        Verilated::overWidthError("out_ready");
    }
}
#endif  // VL_DEBUG
