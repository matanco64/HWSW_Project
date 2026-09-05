`default_nettype none
// Module: fp64_rcp_nr
// Purpose: IEEE-754 binary64 reciprocal (1.0 / a), correctly rounded RNE — bit-exact to
//          numpy float64 division for every input, including subnormal inputs, subnormal
//          results (with denormalized rounding) and overflow to infinity. Canonical qNaN
//          0x7FF8000000000000 on any NaN input. Flags {invalid, divzero, overflow,
//          underflow} per tb/unit/fp_helpers.ref_op ("rcp").
//
// Contract (docs/rtl_contracts.md): LATENCY = 22 fixed for every input (specials padded),
// II = 2 enforced by the reservation table and asserted by SVA below. No back-pressure.
// rst_n clears the valid pipeline only (data registers may carry X until first fill;
// out_valid gating makes that harmless).
//
// Algorithm (docs/uarch.md §1/§4, Borges arXiv 2112.14321, research/fp64-unit-sourcing.md):
//   1. Normalize: a = (-1)^s * m * 2^e, m in [1,2) as UQ1.52 (M, 53 b). Subnormal inputs
//      are normalized with a priority encoder (e down to -1074).
//   2. Seed: 1024 x 20 b ROM (UQ1.19), indexed by the top 10 fraction bits of m; each entry
//      is round(2^19 / midpoint(interval)). Seed relative error < 2^-9.9.
//   3. Three Newton–Raphson iterations y' = y*(2 - m*y) in internal fixed point, widths
//      growing UQ1.28 -> UQ1.57 -> UQ1.57 (no IEEE rounding between iterations). Since
//      y*(2-m*y) <= 1/m for all y, every iterate stays strictly below 1.0.
//   4. Compensated final step: r = 1 - m*y3 via the EXACT widened product m*y3 (UQ2.109);
//      |r| < 2^-54 (checked by an assertion, empirical max 2^-56). y' = y3 + y3*r in
//      UQ1.62 => |y' - 1/m| < 1.3*2^-62.
//   5. RNE by residual sign at the rounding boundary (the Borges technique): the result
//      significand at precision p+1 bits (p = 52 normal, 51/50 for the denormalization
//      shift of 1/2 — 1/|a| >= 2^-1024, so the shift never exceeds 2) is the integer
//      nearest X = 2^(53+p)/M. Candidate C = round(y'*2^(p+1)); then the exact residuals
//      A1 = 2^(54+p) + M - 2*C*M and A2 = A1 - 2M give sign(X-(C-1/2)) and sign(X-(C+1/2)):
//      A1 < 0 => C-1, A2 > 0 => C+1, else C. Ties are impossible: 2^(54+p) = (2C+-1)*M
//      would force M to be a power of two, and those take the exact bypass path. |C - X|
//      <= 0.5 + 2^-8.6 << 1.5, so C-1/C/C+1 always covers the true result: rounding is
//      correct by construction whenever the exact-product/residual arithmetic is exact,
//      which it is (plain integer multiplies). Validated bit-exactly against numpy on
//      2M+ random/directed vectors and factoring-constructed near-boundary cases.
//   6. Exact bypass: a = +-2^k (M = 2^52) returns the exact reciprocal (or inf/subnormal
//      2^-1023) without touching the NR path; NaN/inf/zero likewise, all at LATENCY.
//
// Rounding-boundary exactness argument in short: for M != 2^52 the reciprocal is never
// exactly representable and never a tie, inexact is always set, so underflow = "result
// subnormal" and the residual sign fully decides RNE.
//
// Pipeline: 12 compute stages (unpack/ROM/3xNR/compensate/candidate/residual+pack) plus a
// 10-deep result delay line pads the latency to exactly 22 for every input. The datapath
// is fully pipelined (II = 1 capable), so the contract II = 2 is honored by construction;
// the interleave sharing of uarch §1 is a PPA optimization left to the ppa stage.
module fp64_rcp_nr (
    input  logic        clk,        // System clock
    input  logic        rst_n,      // Sync active-low; clears valid pipeline only
    input  logic        in_valid,   // One operation issued this cycle (II >= 2 apart)
    input  logic [63:0] a,          // IEEE-754 binary64 operand
    output logic        out_valid,  // Exactly LATENCY cycles after in_valid
    output logic [63:0] result,     // binary64 RNE 1.0/a, full subnormals, canonical qNaN
    output logic [3:0]  flags       // {invalid, divzero, overflow, underflow}
);

    // LATENCY = 22 (rtl_contracts.md: exported localparam; re-run docs/schedule_model.py
    // if this changes). II = 2 asserted below.
    localparam int unsigned LATENCY = 22;
    localparam int unsigned NSTAGE  = 12;               // compute stages
    localparam int unsigned NDELAY  = LATENCY - NSTAGE; // result delay stages

    localparam logic [63:0] QNAN = 64'h7FF8_0000_0000_0000; // Canonical quiet NaN

    // ------------------------------------------------------------------------------
    // Valid pipeline (the only state cleared by rst_n)
    // ------------------------------------------------------------------------------
    logic [LATENCY-1:0] valid_q;     // valid_q[k] = op issued k+1 cycles ago
    logic [LATENCY-1:0] valid_next;  // next valid pipeline value

    always_comb begin
        valid_next = {valid_q[LATENCY-2:0], in_valid} & {LATENCY{rst_n}};
    end

    always_ff @(posedge clk) begin
        valid_q <= valid_next;
    end

    assign out_valid = valid_q[LATENCY-1];

    // ------------------------------------------------------------------------------
    // Seed ROM: 1024 x 20 b UQ1.19, entry i = round(2^19 * 2048 / (2049 + 2i))
    // (reciprocal of the interval midpoint). Generated; synchronous 1R read.
    // ------------------------------------------------------------------------------
    logic [19:0] seed_rom [0:1023];  // Reciprocal seed ROM, UQ1.19

    initial begin
        seed_rom[0] = 20'h7FF00;
        seed_rom[1] = 20'h7FD01;
        seed_rom[2] = 20'h7FB03;
        seed_rom[3] = 20'h7F906;
        seed_rom[4] = 20'h7F70A;
        seed_rom[5] = 20'h7F50F;
        seed_rom[6] = 20'h7F315;
        seed_rom[7] = 20'h7F11C;
        seed_rom[8] = 20'h7EF24;
        seed_rom[9] = 20'h7ED2D;
        seed_rom[10] = 20'h7EB37;
        seed_rom[11] = 20'h7E941;
        seed_rom[12] = 20'h7E74D;
        seed_rom[13] = 20'h7E55A;
        seed_rom[14] = 20'h7E368;
        seed_rom[15] = 20'h7E176;
        seed_rom[16] = 20'h7DF86;
        seed_rom[17] = 20'h7DD97;
        seed_rom[18] = 20'h7DBA8;
        seed_rom[19] = 20'h7D9BB;
        seed_rom[20] = 20'h7D7CE;
        seed_rom[21] = 20'h7D5E2;
        seed_rom[22] = 20'h7D3F8;
        seed_rom[23] = 20'h7D20E;
        seed_rom[24] = 20'h7D025;
        seed_rom[25] = 20'h7CE3D;
        seed_rom[26] = 20'h7CC56;
        seed_rom[27] = 20'h7CA70;
        seed_rom[28] = 20'h7C88B;
        seed_rom[29] = 20'h7C6A7;
        seed_rom[30] = 20'h7C4C4;
        seed_rom[31] = 20'h7C2E1;
        seed_rom[32] = 20'h7C100;
        seed_rom[33] = 20'h7BF1F;
        seed_rom[34] = 20'h7BD40;
        seed_rom[35] = 20'h7BB61;
        seed_rom[36] = 20'h7B983;
        seed_rom[37] = 20'h7B7A6;
        seed_rom[38] = 20'h7B5CA;
        seed_rom[39] = 20'h7B3EF;
        seed_rom[40] = 20'h7B215;
        seed_rom[41] = 20'h7B03C;
        seed_rom[42] = 20'h7AE63;
        seed_rom[43] = 20'h7AC8C;
        seed_rom[44] = 20'h7AAB5;
        seed_rom[45] = 20'h7A8DF;
        seed_rom[46] = 20'h7A70A;
        seed_rom[47] = 20'h7A536;
        seed_rom[48] = 20'h7A363;
        seed_rom[49] = 20'h7A191;
        seed_rom[50] = 20'h79FBF;
        seed_rom[51] = 20'h79DEF;
        seed_rom[52] = 20'h79C1F;
        seed_rom[53] = 20'h79A50;
        seed_rom[54] = 20'h79882;
        seed_rom[55] = 20'h796B5;
        seed_rom[56] = 20'h794E9;
        seed_rom[57] = 20'h7931D;
        seed_rom[58] = 20'h79153;
        seed_rom[59] = 20'h78F89;
        seed_rom[60] = 20'h78DC0;
        seed_rom[61] = 20'h78BF8;
        seed_rom[62] = 20'h78A31;
        seed_rom[63] = 20'h7886A;
        seed_rom[64] = 20'h786A5;
        seed_rom[65] = 20'h784E0;
        seed_rom[66] = 20'h7831C;
        seed_rom[67] = 20'h78159;
        seed_rom[68] = 20'h77F97;
        seed_rom[69] = 20'h77DD6;
        seed_rom[70] = 20'h77C15;
        seed_rom[71] = 20'h77A55;
        seed_rom[72] = 20'h77896;
        seed_rom[73] = 20'h776D8;
        seed_rom[74] = 20'h7751B;
        seed_rom[75] = 20'h7735E;
        seed_rom[76] = 20'h771A3;
        seed_rom[77] = 20'h76FE8;
        seed_rom[78] = 20'h76E2E;
        seed_rom[79] = 20'h76C74;
        seed_rom[80] = 20'h76ABC;
        seed_rom[81] = 20'h76904;
        seed_rom[82] = 20'h7674D;
        seed_rom[83] = 20'h76597;
        seed_rom[84] = 20'h763E2;
        seed_rom[85] = 20'h7622D;
        seed_rom[86] = 20'h7607A;
        seed_rom[87] = 20'h75EC7;
        seed_rom[88] = 20'h75D15;
        seed_rom[89] = 20'h75B63;
        seed_rom[90] = 20'h759B3;
        seed_rom[91] = 20'h75803;
        seed_rom[92] = 20'h75654;
        seed_rom[93] = 20'h754A5;
        seed_rom[94] = 20'h752F8;
        seed_rom[95] = 20'h7514B;
        seed_rom[96] = 20'h74F9F;
        seed_rom[97] = 20'h74DF4;
        seed_rom[98] = 20'h74C49;
        seed_rom[99] = 20'h74AA0;
        seed_rom[100] = 20'h748F7;
        seed_rom[101] = 20'h7474F;
        seed_rom[102] = 20'h745A7;
        seed_rom[103] = 20'h74400;
        seed_rom[104] = 20'h7425B;
        seed_rom[105] = 20'h740B5;
        seed_rom[106] = 20'h73F11;
        seed_rom[107] = 20'h73D6D;
        seed_rom[108] = 20'h73BCA;
        seed_rom[109] = 20'h73A28;
        seed_rom[110] = 20'h73886;
        seed_rom[111] = 20'h736E6;
        seed_rom[112] = 20'h73546;
        seed_rom[113] = 20'h733A6;
        seed_rom[114] = 20'h73208;
        seed_rom[115] = 20'h7306A;
        seed_rom[116] = 20'h72ECD;
        seed_rom[117] = 20'h72D31;
        seed_rom[118] = 20'h72B95;
        seed_rom[119] = 20'h729FA;
        seed_rom[120] = 20'h72860;
        seed_rom[121] = 20'h726C6;
        seed_rom[122] = 20'h7252D;
        seed_rom[123] = 20'h72395;
        seed_rom[124] = 20'h721FE;
        seed_rom[125] = 20'h72067;
        seed_rom[126] = 20'h71ED1;
        seed_rom[127] = 20'h71D3C;
        seed_rom[128] = 20'h71BA8;
        seed_rom[129] = 20'h71A14;
        seed_rom[130] = 20'h71881;
        seed_rom[131] = 20'h716EE;
        seed_rom[132] = 20'h7155C;
        seed_rom[133] = 20'h713CB;
        seed_rom[134] = 20'h7123B;
        seed_rom[135] = 20'h710AB;
        seed_rom[136] = 20'h70F1C;
        seed_rom[137] = 20'h70D8E;
        seed_rom[138] = 20'h70C00;
        seed_rom[139] = 20'h70A74;
        seed_rom[140] = 20'h708E7;
        seed_rom[141] = 20'h7075C;
        seed_rom[142] = 20'h705D1;
        seed_rom[143] = 20'h70447;
        seed_rom[144] = 20'h702BD;
        seed_rom[145] = 20'h70134;
        seed_rom[146] = 20'h6FFAC;
        seed_rom[147] = 20'h6FE24;
        seed_rom[148] = 20'h6FC9E;
        seed_rom[149] = 20'h6FB17;
        seed_rom[150] = 20'h6F992;
        seed_rom[151] = 20'h6F80D;
        seed_rom[152] = 20'h6F689;
        seed_rom[153] = 20'h6F505;
        seed_rom[154] = 20'h6F382;
        seed_rom[155] = 20'h6F200;
        seed_rom[156] = 20'h6F07F;
        seed_rom[157] = 20'h6EEFE;
        seed_rom[158] = 20'h6ED7D;
        seed_rom[159] = 20'h6EBFE;
        seed_rom[160] = 20'h6EA7F;
        seed_rom[161] = 20'h6E901;
        seed_rom[162] = 20'h6E783;
        seed_rom[163] = 20'h6E606;
        seed_rom[164] = 20'h6E489;
        seed_rom[165] = 20'h6E30E;
        seed_rom[166] = 20'h6E193;
        seed_rom[167] = 20'h6E018;
        seed_rom[168] = 20'h6DE9E;
        seed_rom[169] = 20'h6DD25;
        seed_rom[170] = 20'h6DBAC;
        seed_rom[171] = 20'h6DA34;
        seed_rom[172] = 20'h6D8BD;
        seed_rom[173] = 20'h6D746;
        seed_rom[174] = 20'h6D5D0;
        seed_rom[175] = 20'h6D45B;
        seed_rom[176] = 20'h6D2E6;
        seed_rom[177] = 20'h6D172;
        seed_rom[178] = 20'h6CFFE;
        seed_rom[179] = 20'h6CE8B;
        seed_rom[180] = 20'h6CD19;
        seed_rom[181] = 20'h6CBA7;
        seed_rom[182] = 20'h6CA36;
        seed_rom[183] = 20'h6C8C6;
        seed_rom[184] = 20'h6C756;
        seed_rom[185] = 20'h6C5E6;
        seed_rom[186] = 20'h6C478;
        seed_rom[187] = 20'h6C30A;
        seed_rom[188] = 20'h6C19C;
        seed_rom[189] = 20'h6C02F;
        seed_rom[190] = 20'h6BEC3;
        seed_rom[191] = 20'h6BD57;
        seed_rom[192] = 20'h6BBEC;
        seed_rom[193] = 20'h6BA82;
        seed_rom[194] = 20'h6B918;
        seed_rom[195] = 20'h6B7AF;
        seed_rom[196] = 20'h6B646;
        seed_rom[197] = 20'h6B4DE;
        seed_rom[198] = 20'h6B376;
        seed_rom[199] = 20'h6B20F;
        seed_rom[200] = 20'h6B0A9;
        seed_rom[201] = 20'h6AF43;
        seed_rom[202] = 20'h6ADDE;
        seed_rom[203] = 20'h6AC79;
        seed_rom[204] = 20'h6AB15;
        seed_rom[205] = 20'h6A9B2;
        seed_rom[206] = 20'h6A84F;
        seed_rom[207] = 20'h6A6ED;
        seed_rom[208] = 20'h6A58B;
        seed_rom[209] = 20'h6A42A;
        seed_rom[210] = 20'h6A2C9;
        seed_rom[211] = 20'h6A169;
        seed_rom[212] = 20'h6A00A;
        seed_rom[213] = 20'h69EAB;
        seed_rom[214] = 20'h69D4D;
        seed_rom[215] = 20'h69BEF;
        seed_rom[216] = 20'h69A92;
        seed_rom[217] = 20'h69935;
        seed_rom[218] = 20'h697D9;
        seed_rom[219] = 20'h6967E;
        seed_rom[220] = 20'h69523;
        seed_rom[221] = 20'h693C9;
        seed_rom[222] = 20'h6926F;
        seed_rom[223] = 20'h69115;
        seed_rom[224] = 20'h68FBD;
        seed_rom[225] = 20'h68E65;
        seed_rom[226] = 20'h68D0D;
        seed_rom[227] = 20'h68BB6;
        seed_rom[228] = 20'h68A5F;
        seed_rom[229] = 20'h68909;
        seed_rom[230] = 20'h687B4;
        seed_rom[231] = 20'h6865F;
        seed_rom[232] = 20'h6850B;
        seed_rom[233] = 20'h683B7;
        seed_rom[234] = 20'h68264;
        seed_rom[235] = 20'h68111;
        seed_rom[236] = 20'h67FBF;
        seed_rom[237] = 20'h67E6D;
        seed_rom[238] = 20'h67D1C;
        seed_rom[239] = 20'h67BCC;
        seed_rom[240] = 20'h67A7C;
        seed_rom[241] = 20'h6792C;
        seed_rom[242] = 20'h677DD;
        seed_rom[243] = 20'h6768F;
        seed_rom[244] = 20'h67541;
        seed_rom[245] = 20'h673F3;
        seed_rom[246] = 20'h672A7;
        seed_rom[247] = 20'h6715A;
        seed_rom[248] = 20'h6700E;
        seed_rom[249] = 20'h66EC3;
        seed_rom[250] = 20'h66D78;
        seed_rom[251] = 20'h66C2E;
        seed_rom[252] = 20'h66AE4;
        seed_rom[253] = 20'h6699B;
        seed_rom[254] = 20'h66852;
        seed_rom[255] = 20'h6670A;
        seed_rom[256] = 20'h665C3;
        seed_rom[257] = 20'h6647B;
        seed_rom[258] = 20'h66335;
        seed_rom[259] = 20'h661EF;
        seed_rom[260] = 20'h660A9;
        seed_rom[261] = 20'h65F64;
        seed_rom[262] = 20'h65E1F;
        seed_rom[263] = 20'h65CDB;
        seed_rom[264] = 20'h65B97;
        seed_rom[265] = 20'h65A54;
        seed_rom[266] = 20'h65912;
        seed_rom[267] = 20'h657D0;
        seed_rom[268] = 20'h6568E;
        seed_rom[269] = 20'h6554D;
        seed_rom[270] = 20'h6540C;
        seed_rom[271] = 20'h652CC;
        seed_rom[272] = 20'h6518C;
        seed_rom[273] = 20'h6504D;
        seed_rom[274] = 20'h64F0F;
        seed_rom[275] = 20'h64DD1;
        seed_rom[276] = 20'h64C93;
        seed_rom[277] = 20'h64B56;
        seed_rom[278] = 20'h64A19;
        seed_rom[279] = 20'h648DD;
        seed_rom[280] = 20'h647A1;
        seed_rom[281] = 20'h64666;
        seed_rom[282] = 20'h6452B;
        seed_rom[283] = 20'h643F1;
        seed_rom[284] = 20'h642B7;
        seed_rom[285] = 20'h6417E;
        seed_rom[286] = 20'h64045;
        seed_rom[287] = 20'h63F0C;
        seed_rom[288] = 20'h63DD5;
        seed_rom[289] = 20'h63C9D;
        seed_rom[290] = 20'h63B66;
        seed_rom[291] = 20'h63A30;
        seed_rom[292] = 20'h638FA;
        seed_rom[293] = 20'h637C4;
        seed_rom[294] = 20'h6368F;
        seed_rom[295] = 20'h6355B;
        seed_rom[296] = 20'h63426;
        seed_rom[297] = 20'h632F3;
        seed_rom[298] = 20'h631C0;
        seed_rom[299] = 20'h6308D;
        seed_rom[300] = 20'h62F5B;
        seed_rom[301] = 20'h62E29;
        seed_rom[302] = 20'h62CF7;
        seed_rom[303] = 20'h62BC7;
        seed_rom[304] = 20'h62A96;
        seed_rom[305] = 20'h62966;
        seed_rom[306] = 20'h62837;
        seed_rom[307] = 20'h62708;
        seed_rom[308] = 20'h625D9;
        seed_rom[309] = 20'h624AB;
        seed_rom[310] = 20'h6237D;
        seed_rom[311] = 20'h62250;
        seed_rom[312] = 20'h62123;
        seed_rom[313] = 20'h61FF7;
        seed_rom[314] = 20'h61ECB;
        seed_rom[315] = 20'h61D9F;
        seed_rom[316] = 20'h61C74;
        seed_rom[317] = 20'h61B4A;
        seed_rom[318] = 20'h61A20;
        seed_rom[319] = 20'h618F6;
        seed_rom[320] = 20'h617CD;
        seed_rom[321] = 20'h616A4;
        seed_rom[322] = 20'h6157C;
        seed_rom[323] = 20'h61454;
        seed_rom[324] = 20'h6132D;
        seed_rom[325] = 20'h61206;
        seed_rom[326] = 20'h610DF;
        seed_rom[327] = 20'h60FB9;
        seed_rom[328] = 20'h60E93;
        seed_rom[329] = 20'h60D6E;
        seed_rom[330] = 20'h60C49;
        seed_rom[331] = 20'h60B25;
        seed_rom[332] = 20'h60A01;
        seed_rom[333] = 20'h608DD;
        seed_rom[334] = 20'h607BA;
        seed_rom[335] = 20'h60697;
        seed_rom[336] = 20'h60575;
        seed_rom[337] = 20'h60453;
        seed_rom[338] = 20'h60332;
        seed_rom[339] = 20'h60211;
        seed_rom[340] = 20'h600F0;
        seed_rom[341] = 20'h5FFD0;
        seed_rom[342] = 20'h5FEB0;
        seed_rom[343] = 20'h5FD91;
        seed_rom[344] = 20'h5FC72;
        seed_rom[345] = 20'h5FB54;
        seed_rom[346] = 20'h5FA36;
        seed_rom[347] = 20'h5F918;
        seed_rom[348] = 20'h5F7FB;
        seed_rom[349] = 20'h5F6DE;
        seed_rom[350] = 20'h5F5C2;
        seed_rom[351] = 20'h5F4A6;
        seed_rom[352] = 20'h5F38A;
        seed_rom[353] = 20'h5F26F;
        seed_rom[354] = 20'h5F154;
        seed_rom[355] = 20'h5F03A;
        seed_rom[356] = 20'h5EF20;
        seed_rom[357] = 20'h5EE06;
        seed_rom[358] = 20'h5ECED;
        seed_rom[359] = 20'h5EBD5;
        seed_rom[360] = 20'h5EABC;
        seed_rom[361] = 20'h5E9A5;
        seed_rom[362] = 20'h5E88D;
        seed_rom[363] = 20'h5E776;
        seed_rom[364] = 20'h5E65F;
        seed_rom[365] = 20'h5E549;
        seed_rom[366] = 20'h5E433;
        seed_rom[367] = 20'h5E31E;
        seed_rom[368] = 20'h5E209;
        seed_rom[369] = 20'h5E0F4;
        seed_rom[370] = 20'h5DFE0;
        seed_rom[371] = 20'h5DECC;
        seed_rom[372] = 20'h5DDB8;
        seed_rom[373] = 20'h5DCA5;
        seed_rom[374] = 20'h5DB93;
        seed_rom[375] = 20'h5DA80;
        seed_rom[376] = 20'h5D96E;
        seed_rom[377] = 20'h5D85D;
        seed_rom[378] = 20'h5D74C;
        seed_rom[379] = 20'h5D63B;
        seed_rom[380] = 20'h5D52B;
        seed_rom[381] = 20'h5D41B;
        seed_rom[382] = 20'h5D30B;
        seed_rom[383] = 20'h5D1FC;
        seed_rom[384] = 20'h5D0ED;
        seed_rom[385] = 20'h5CFDF;
        seed_rom[386] = 20'h5CED1;
        seed_rom[387] = 20'h5CDC3;
        seed_rom[388] = 20'h5CCB6;
        seed_rom[389] = 20'h5CBA9;
        seed_rom[390] = 20'h5CA9C;
        seed_rom[391] = 20'h5C990;
        seed_rom[392] = 20'h5C884;
        seed_rom[393] = 20'h5C779;
        seed_rom[394] = 20'h5C66E;
        seed_rom[395] = 20'h5C563;
        seed_rom[396] = 20'h5C459;
        seed_rom[397] = 20'h5C34F;
        seed_rom[398] = 20'h5C246;
        seed_rom[399] = 20'h5C13D;
        seed_rom[400] = 20'h5C034;
        seed_rom[401] = 20'h5BF2B;
        seed_rom[402] = 20'h5BE23;
        seed_rom[403] = 20'h5BD1C;
        seed_rom[404] = 20'h5BC14;
        seed_rom[405] = 20'h5BB0E;
        seed_rom[406] = 20'h5BA07;
        seed_rom[407] = 20'h5B901;
        seed_rom[408] = 20'h5B7FB;
        seed_rom[409] = 20'h5B6F6;
        seed_rom[410] = 20'h5B5F0;
        seed_rom[411] = 20'h5B4EC;
        seed_rom[412] = 20'h5B3E7;
        seed_rom[413] = 20'h5B2E3;
        seed_rom[414] = 20'h5B1E0;
        seed_rom[415] = 20'h5B0DD;
        seed_rom[416] = 20'h5AFDA;
        seed_rom[417] = 20'h5AED7;
        seed_rom[418] = 20'h5ADD5;
        seed_rom[419] = 20'h5ACD3;
        seed_rom[420] = 20'h5ABD2;
        seed_rom[421] = 20'h5AAD0;
        seed_rom[422] = 20'h5A9D0;
        seed_rom[423] = 20'h5A8CF;
        seed_rom[424] = 20'h5A7CF;
        seed_rom[425] = 20'h5A6D0;
        seed_rom[426] = 20'h5A5D0;
        seed_rom[427] = 20'h5A4D1;
        seed_rom[428] = 20'h5A3D3;
        seed_rom[429] = 20'h5A2D4;
        seed_rom[430] = 20'h5A1D6;
        seed_rom[431] = 20'h5A0D9;
        seed_rom[432] = 20'h59FDB;
        seed_rom[433] = 20'h59EDF;
        seed_rom[434] = 20'h59DE2;
        seed_rom[435] = 20'h59CE6;
        seed_rom[436] = 20'h59BEA;
        seed_rom[437] = 20'h59AEE;
        seed_rom[438] = 20'h599F3;
        seed_rom[439] = 20'h598F8;
        seed_rom[440] = 20'h597FE;
        seed_rom[441] = 20'h59704;
        seed_rom[442] = 20'h5960A;
        seed_rom[443] = 20'h59510;
        seed_rom[444] = 20'h59417;
        seed_rom[445] = 20'h5931F;
        seed_rom[446] = 20'h59226;
        seed_rom[447] = 20'h5912E;
        seed_rom[448] = 20'h59036;
        seed_rom[449] = 20'h58F3F;
        seed_rom[450] = 20'h58E48;
        seed_rom[451] = 20'h58D51;
        seed_rom[452] = 20'h58C5B;
        seed_rom[453] = 20'h58B64;
        seed_rom[454] = 20'h58A6F;
        seed_rom[455] = 20'h58979;
        seed_rom[456] = 20'h58884;
        seed_rom[457] = 20'h5878F;
        seed_rom[458] = 20'h5869B;
        seed_rom[459] = 20'h585A7;
        seed_rom[460] = 20'h584B3;
        seed_rom[461] = 20'h583C0;
        seed_rom[462] = 20'h582CC;
        seed_rom[463] = 20'h581DA;
        seed_rom[464] = 20'h580E7;
        seed_rom[465] = 20'h57FF5;
        seed_rom[466] = 20'h57F03;
        seed_rom[467] = 20'h57E12;
        seed_rom[468] = 20'h57D21;
        seed_rom[469] = 20'h57C30;
        seed_rom[470] = 20'h57B3F;
        seed_rom[471] = 20'h57A4F;
        seed_rom[472] = 20'h5795F;
        seed_rom[473] = 20'h5786F;
        seed_rom[474] = 20'h57780;
        seed_rom[475] = 20'h57691;
        seed_rom[476] = 20'h575A3;
        seed_rom[477] = 20'h574B4;
        seed_rom[478] = 20'h573C6;
        seed_rom[479] = 20'h572D9;
        seed_rom[480] = 20'h571EB;
        seed_rom[481] = 20'h570FE;
        seed_rom[482] = 20'h57012;
        seed_rom[483] = 20'h56F25;
        seed_rom[484] = 20'h56E39;
        seed_rom[485] = 20'h56D4D;
        seed_rom[486] = 20'h56C62;
        seed_rom[487] = 20'h56B77;
        seed_rom[488] = 20'h56A8C;
        seed_rom[489] = 20'h569A1;
        seed_rom[490] = 20'h568B7;
        seed_rom[491] = 20'h567CD;
        seed_rom[492] = 20'h566E4;
        seed_rom[493] = 20'h565FA;
        seed_rom[494] = 20'h56511;
        seed_rom[495] = 20'h56429;
        seed_rom[496] = 20'h56340;
        seed_rom[497] = 20'h56258;
        seed_rom[498] = 20'h56171;
        seed_rom[499] = 20'h56089;
        seed_rom[500] = 20'h55FA2;
        seed_rom[501] = 20'h55EBB;
        seed_rom[502] = 20'h55DD5;
        seed_rom[503] = 20'h55CEE;
        seed_rom[504] = 20'h55C08;
        seed_rom[505] = 20'h55B23;
        seed_rom[506] = 20'h55A3D;
        seed_rom[507] = 20'h55958;
        seed_rom[508] = 20'h55874;
        seed_rom[509] = 20'h5578F;
        seed_rom[510] = 20'h556AB;
        seed_rom[511] = 20'h555C7;
        seed_rom[512] = 20'h554E4;
        seed_rom[513] = 20'h55400;
        seed_rom[514] = 20'h5531D;
        seed_rom[515] = 20'h5523B;
        seed_rom[516] = 20'h55158;
        seed_rom[517] = 20'h55076;
        seed_rom[518] = 20'h54F94;
        seed_rom[519] = 20'h54EB3;
        seed_rom[520] = 20'h54DD2;
        seed_rom[521] = 20'h54CF1;
        seed_rom[522] = 20'h54C10;
        seed_rom[523] = 20'h54B30;
        seed_rom[524] = 20'h54A50;
        seed_rom[525] = 20'h54970;
        seed_rom[526] = 20'h54891;
        seed_rom[527] = 20'h547B1;
        seed_rom[528] = 20'h546D3;
        seed_rom[529] = 20'h545F4;
        seed_rom[530] = 20'h54516;
        seed_rom[531] = 20'h54438;
        seed_rom[532] = 20'h5435A;
        seed_rom[533] = 20'h5427C;
        seed_rom[534] = 20'h5419F;
        seed_rom[535] = 20'h540C2;
        seed_rom[536] = 20'h53FE6;
        seed_rom[537] = 20'h53F09;
        seed_rom[538] = 20'h53E2D;
        seed_rom[539] = 20'h53D52;
        seed_rom[540] = 20'h53C76;
        seed_rom[541] = 20'h53B9B;
        seed_rom[542] = 20'h53AC0;
        seed_rom[543] = 20'h539E5;
        seed_rom[544] = 20'h5390B;
        seed_rom[545] = 20'h53831;
        seed_rom[546] = 20'h53757;
        seed_rom[547] = 20'h5367E;
        seed_rom[548] = 20'h535A4;
        seed_rom[549] = 20'h534CB;
        seed_rom[550] = 20'h533F3;
        seed_rom[551] = 20'h5331A;
        seed_rom[552] = 20'h53242;
        seed_rom[553] = 20'h5316A;
        seed_rom[554] = 20'h53093;
        seed_rom[555] = 20'h52FBB;
        seed_rom[556] = 20'h52EE4;
        seed_rom[557] = 20'h52E0D;
        seed_rom[558] = 20'h52D37;
        seed_rom[559] = 20'h52C61;
        seed_rom[560] = 20'h52B8B;
        seed_rom[561] = 20'h52AB5;
        seed_rom[562] = 20'h529E0;
        seed_rom[563] = 20'h5290A;
        seed_rom[564] = 20'h52836;
        seed_rom[565] = 20'h52761;
        seed_rom[566] = 20'h5268D;
        seed_rom[567] = 20'h525B8;
        seed_rom[568] = 20'h524E5;
        seed_rom[569] = 20'h52411;
        seed_rom[570] = 20'h5233E;
        seed_rom[571] = 20'h5226B;
        seed_rom[572] = 20'h52198;
        seed_rom[573] = 20'h520C5;
        seed_rom[574] = 20'h51FF3;
        seed_rom[575] = 20'h51F21;
        seed_rom[576] = 20'h51E4F;
        seed_rom[577] = 20'h51D7E;
        seed_rom[578] = 20'h51CAD;
        seed_rom[579] = 20'h51BDC;
        seed_rom[580] = 20'h51B0B;
        seed_rom[581] = 20'h51A3B;
        seed_rom[582] = 20'h5196B;
        seed_rom[583] = 20'h5189B;
        seed_rom[584] = 20'h517CB;
        seed_rom[585] = 20'h516FC;
        seed_rom[586] = 20'h5162D;
        seed_rom[587] = 20'h5155E;
        seed_rom[588] = 20'h5148F;
        seed_rom[589] = 20'h513C1;
        seed_rom[590] = 20'h512F3;
        seed_rom[591] = 20'h51225;
        seed_rom[592] = 20'h51157;
        seed_rom[593] = 20'h5108A;
        seed_rom[594] = 20'h50FBD;
        seed_rom[595] = 20'h50EF0;
        seed_rom[596] = 20'h50E24;
        seed_rom[597] = 20'h50D57;
        seed_rom[598] = 20'h50C8B;
        seed_rom[599] = 20'h50BBF;
        seed_rom[600] = 20'h50AF4;
        seed_rom[601] = 20'h50A28;
        seed_rom[602] = 20'h5095D;
        seed_rom[603] = 20'h50893;
        seed_rom[604] = 20'h507C8;
        seed_rom[605] = 20'h506FE;
        seed_rom[606] = 20'h50634;
        seed_rom[607] = 20'h5056A;
        seed_rom[608] = 20'h504A0;
        seed_rom[609] = 20'h503D7;
        seed_rom[610] = 20'h5030E;
        seed_rom[611] = 20'h50245;
        seed_rom[612] = 20'h5017C;
        seed_rom[613] = 20'h500B4;
        seed_rom[614] = 20'h4FFEC;
        seed_rom[615] = 20'h4FF24;
        seed_rom[616] = 20'h4FE5D;
        seed_rom[617] = 20'h4FD95;
        seed_rom[618] = 20'h4FCCE;
        seed_rom[619] = 20'h4FC07;
        seed_rom[620] = 20'h4FB41;
        seed_rom[621] = 20'h4FA7A;
        seed_rom[622] = 20'h4F9B4;
        seed_rom[623] = 20'h4F8EE;
        seed_rom[624] = 20'h4F828;
        seed_rom[625] = 20'h4F763;
        seed_rom[626] = 20'h4F69E;
        seed_rom[627] = 20'h4F5D9;
        seed_rom[628] = 20'h4F514;
        seed_rom[629] = 20'h4F450;
        seed_rom[630] = 20'h4F38B;
        seed_rom[631] = 20'h4F2C7;
        seed_rom[632] = 20'h4F204;
        seed_rom[633] = 20'h4F140;
        seed_rom[634] = 20'h4F07D;
        seed_rom[635] = 20'h4EFBA;
        seed_rom[636] = 20'h4EEF7;
        seed_rom[637] = 20'h4EE34;
        seed_rom[638] = 20'h4ED72;
        seed_rom[639] = 20'h4ECB0;
        seed_rom[640] = 20'h4EBEE;
        seed_rom[641] = 20'h4EB2C;
        seed_rom[642] = 20'h4EA6B;
        seed_rom[643] = 20'h4E9AA;
        seed_rom[644] = 20'h4E8E9;
        seed_rom[645] = 20'h4E828;
        seed_rom[646] = 20'h4E767;
        seed_rom[647] = 20'h4E6A7;
        seed_rom[648] = 20'h4E5E7;
        seed_rom[649] = 20'h4E527;
        seed_rom[650] = 20'h4E468;
        seed_rom[651] = 20'h4E3A8;
        seed_rom[652] = 20'h4E2E9;
        seed_rom[653] = 20'h4E22A;
        seed_rom[654] = 20'h4E16C;
        seed_rom[655] = 20'h4E0AD;
        seed_rom[656] = 20'h4DFEF;
        seed_rom[657] = 20'h4DF31;
        seed_rom[658] = 20'h4DE73;
        seed_rom[659] = 20'h4DDB6;
        seed_rom[660] = 20'h4DCF8;
        seed_rom[661] = 20'h4DC3B;
        seed_rom[662] = 20'h4DB7E;
        seed_rom[663] = 20'h4DAC2;
        seed_rom[664] = 20'h4DA05;
        seed_rom[665] = 20'h4D949;
        seed_rom[666] = 20'h4D88D;
        seed_rom[667] = 20'h4D7D1;
        seed_rom[668] = 20'h4D716;
        seed_rom[669] = 20'h4D65B;
        seed_rom[670] = 20'h4D59F;
        seed_rom[671] = 20'h4D4E5;
        seed_rom[672] = 20'h4D42A;
        seed_rom[673] = 20'h4D370;
        seed_rom[674] = 20'h4D2B5;
        seed_rom[675] = 20'h4D1FB;
        seed_rom[676] = 20'h4D142;
        seed_rom[677] = 20'h4D088;
        seed_rom[678] = 20'h4CFCF;
        seed_rom[679] = 20'h4CF16;
        seed_rom[680] = 20'h4CE5D;
        seed_rom[681] = 20'h4CDA4;
        seed_rom[682] = 20'h4CCEC;
        seed_rom[683] = 20'h4CC33;
        seed_rom[684] = 20'h4CB7B;
        seed_rom[685] = 20'h4CAC3;
        seed_rom[686] = 20'h4CA0C;
        seed_rom[687] = 20'h4C954;
        seed_rom[688] = 20'h4C89D;
        seed_rom[689] = 20'h4C7E6;
        seed_rom[690] = 20'h4C730;
        seed_rom[691] = 20'h4C679;
        seed_rom[692] = 20'h4C5C3;
        seed_rom[693] = 20'h4C50D;
        seed_rom[694] = 20'h4C457;
        seed_rom[695] = 20'h4C3A1;
        seed_rom[696] = 20'h4C2EC;
        seed_rom[697] = 20'h4C236;
        seed_rom[698] = 20'h4C181;
        seed_rom[699] = 20'h4C0CC;
        seed_rom[700] = 20'h4C018;
        seed_rom[701] = 20'h4BF63;
        seed_rom[702] = 20'h4BEAF;
        seed_rom[703] = 20'h4BDFB;
        seed_rom[704] = 20'h4BD47;
        seed_rom[705] = 20'h4BC94;
        seed_rom[706] = 20'h4BBE0;
        seed_rom[707] = 20'h4BB2D;
        seed_rom[708] = 20'h4BA7A;
        seed_rom[709] = 20'h4B9C7;
        seed_rom[710] = 20'h4B915;
        seed_rom[711] = 20'h4B863;
        seed_rom[712] = 20'h4B7B0;
        seed_rom[713] = 20'h4B6FE;
        seed_rom[714] = 20'h4B64D;
        seed_rom[715] = 20'h4B59B;
        seed_rom[716] = 20'h4B4EA;
        seed_rom[717] = 20'h4B439;
        seed_rom[718] = 20'h4B388;
        seed_rom[719] = 20'h4B2D7;
        seed_rom[720] = 20'h4B227;
        seed_rom[721] = 20'h4B176;
        seed_rom[722] = 20'h4B0C6;
        seed_rom[723] = 20'h4B016;
        seed_rom[724] = 20'h4AF67;
        seed_rom[725] = 20'h4AEB7;
        seed_rom[726] = 20'h4AE08;
        seed_rom[727] = 20'h4AD59;
        seed_rom[728] = 20'h4ACAA;
        seed_rom[729] = 20'h4ABFB;
        seed_rom[730] = 20'h4AB4D;
        seed_rom[731] = 20'h4AA9E;
        seed_rom[732] = 20'h4A9F0;
        seed_rom[733] = 20'h4A942;
        seed_rom[734] = 20'h4A894;
        seed_rom[735] = 20'h4A7E7;
        seed_rom[736] = 20'h4A73A;
        seed_rom[737] = 20'h4A68D;
        seed_rom[738] = 20'h4A5E0;
        seed_rom[739] = 20'h4A533;
        seed_rom[740] = 20'h4A486;
        seed_rom[741] = 20'h4A3DA;
        seed_rom[742] = 20'h4A32E;
        seed_rom[743] = 20'h4A282;
        seed_rom[744] = 20'h4A1D6;
        seed_rom[745] = 20'h4A12B;
        seed_rom[746] = 20'h4A07F;
        seed_rom[747] = 20'h49FD4;
        seed_rom[748] = 20'h49F29;
        seed_rom[749] = 20'h49E7E;
        seed_rom[750] = 20'h49DD4;
        seed_rom[751] = 20'h49D29;
        seed_rom[752] = 20'h49C7F;
        seed_rom[753] = 20'h49BD5;
        seed_rom[754] = 20'h49B2B;
        seed_rom[755] = 20'h49A82;
        seed_rom[756] = 20'h499D8;
        seed_rom[757] = 20'h4992F;
        seed_rom[758] = 20'h49886;
        seed_rom[759] = 20'h497DD;
        seed_rom[760] = 20'h49734;
        seed_rom[761] = 20'h4968C;
        seed_rom[762] = 20'h495E3;
        seed_rom[763] = 20'h4953B;
        seed_rom[764] = 20'h49493;
        seed_rom[765] = 20'h493EC;
        seed_rom[766] = 20'h49344;
        seed_rom[767] = 20'h4929D;
        seed_rom[768] = 20'h491F6;
        seed_rom[769] = 20'h4914F;
        seed_rom[770] = 20'h490A8;
        seed_rom[771] = 20'h49001;
        seed_rom[772] = 20'h48F5B;
        seed_rom[773] = 20'h48EB4;
        seed_rom[774] = 20'h48E0E;
        seed_rom[775] = 20'h48D68;
        seed_rom[776] = 20'h48CC3;
        seed_rom[777] = 20'h48C1D;
        seed_rom[778] = 20'h48B78;
        seed_rom[779] = 20'h48AD3;
        seed_rom[780] = 20'h48A2E;
        seed_rom[781] = 20'h48989;
        seed_rom[782] = 20'h488E4;
        seed_rom[783] = 20'h48840;
        seed_rom[784] = 20'h4879C;
        seed_rom[785] = 20'h486F8;
        seed_rom[786] = 20'h48654;
        seed_rom[787] = 20'h485B0;
        seed_rom[788] = 20'h4850D;
        seed_rom[789] = 20'h48469;
        seed_rom[790] = 20'h483C6;
        seed_rom[791] = 20'h48323;
        seed_rom[792] = 20'h48280;
        seed_rom[793] = 20'h481DE;
        seed_rom[794] = 20'h4813B;
        seed_rom[795] = 20'h48099;
        seed_rom[796] = 20'h47FF7;
        seed_rom[797] = 20'h47F55;
        seed_rom[798] = 20'h47EB3;
        seed_rom[799] = 20'h47E12;
        seed_rom[800] = 20'h47D70;
        seed_rom[801] = 20'h47CCF;
        seed_rom[802] = 20'h47C2E;
        seed_rom[803] = 20'h47B8D;
        seed_rom[804] = 20'h47AED;
        seed_rom[805] = 20'h47A4C;
        seed_rom[806] = 20'h479AC;
        seed_rom[807] = 20'h4790C;
        seed_rom[808] = 20'h4786C;
        seed_rom[809] = 20'h477CC;
        seed_rom[810] = 20'h4772C;
        seed_rom[811] = 20'h4768D;
        seed_rom[812] = 20'h475EE;
        seed_rom[813] = 20'h4754F;
        seed_rom[814] = 20'h474B0;
        seed_rom[815] = 20'h47411;
        seed_rom[816] = 20'h47372;
        seed_rom[817] = 20'h472D4;
        seed_rom[818] = 20'h47236;
        seed_rom[819] = 20'h47198;
        seed_rom[820] = 20'h470FA;
        seed_rom[821] = 20'h4705C;
        seed_rom[822] = 20'h46FBF;
        seed_rom[823] = 20'h46F21;
        seed_rom[824] = 20'h46E84;
        seed_rom[825] = 20'h46DE7;
        seed_rom[826] = 20'h46D4A;
        seed_rom[827] = 20'h46CAD;
        seed_rom[828] = 20'h46C11;
        seed_rom[829] = 20'h46B75;
        seed_rom[830] = 20'h46AD8;
        seed_rom[831] = 20'h46A3C;
        seed_rom[832] = 20'h469A0;
        seed_rom[833] = 20'h46905;
        seed_rom[834] = 20'h46869;
        seed_rom[835] = 20'h467CE;
        seed_rom[836] = 20'h46733;
        seed_rom[837] = 20'h46698;
        seed_rom[838] = 20'h465FD;
        seed_rom[839] = 20'h46562;
        seed_rom[840] = 20'h464C8;
        seed_rom[841] = 20'h4642D;
        seed_rom[842] = 20'h46393;
        seed_rom[843] = 20'h462F9;
        seed_rom[844] = 20'h4625F;
        seed_rom[845] = 20'h461C6;
        seed_rom[846] = 20'h4612C;
        seed_rom[847] = 20'h46093;
        seed_rom[848] = 20'h45FF9;
        seed_rom[849] = 20'h45F60;
        seed_rom[850] = 20'h45EC8;
        seed_rom[851] = 20'h45E2F;
        seed_rom[852] = 20'h45D96;
        seed_rom[853] = 20'h45CFE;
        seed_rom[854] = 20'h45C66;
        seed_rom[855] = 20'h45BCE;
        seed_rom[856] = 20'h45B36;
        seed_rom[857] = 20'h45A9E;
        seed_rom[858] = 20'h45A06;
        seed_rom[859] = 20'h4596F;
        seed_rom[860] = 20'h458D8;
        seed_rom[861] = 20'h45841;
        seed_rom[862] = 20'h457AA;
        seed_rom[863] = 20'h45713;
        seed_rom[864] = 20'h4567C;
        seed_rom[865] = 20'h455E6;
        seed_rom[866] = 20'h45550;
        seed_rom[867] = 20'h454B9;
        seed_rom[868] = 20'h45423;
        seed_rom[869] = 20'h4538E;
        seed_rom[870] = 20'h452F8;
        seed_rom[871] = 20'h45262;
        seed_rom[872] = 20'h451CD;
        seed_rom[873] = 20'h45138;
        seed_rom[874] = 20'h450A3;
        seed_rom[875] = 20'h4500E;
        seed_rom[876] = 20'h44F79;
        seed_rom[877] = 20'h44EE5;
        seed_rom[878] = 20'h44E50;
        seed_rom[879] = 20'h44DBC;
        seed_rom[880] = 20'h44D28;
        seed_rom[881] = 20'h44C94;
        seed_rom[882] = 20'h44C00;
        seed_rom[883] = 20'h44B6D;
        seed_rom[884] = 20'h44AD9;
        seed_rom[885] = 20'h44A46;
        seed_rom[886] = 20'h449B3;
        seed_rom[887] = 20'h44920;
        seed_rom[888] = 20'h4488D;
        seed_rom[889] = 20'h447FA;
        seed_rom[890] = 20'h44768;
        seed_rom[891] = 20'h446D5;
        seed_rom[892] = 20'h44643;
        seed_rom[893] = 20'h445B1;
        seed_rom[894] = 20'h4451F;
        seed_rom[895] = 20'h4448D;
        seed_rom[896] = 20'h443FB;
        seed_rom[897] = 20'h4436A;
        seed_rom[898] = 20'h442D9;
        seed_rom[899] = 20'h44247;
        seed_rom[900] = 20'h441B6;
        seed_rom[901] = 20'h44126;
        seed_rom[902] = 20'h44095;
        seed_rom[903] = 20'h44004;
        seed_rom[904] = 20'h43F74;
        seed_rom[905] = 20'h43EE4;
        seed_rom[906] = 20'h43E53;
        seed_rom[907] = 20'h43DC3;
        seed_rom[908] = 20'h43D34;
        seed_rom[909] = 20'h43CA4;
        seed_rom[910] = 20'h43C14;
        seed_rom[911] = 20'h43B85;
        seed_rom[912] = 20'h43AF6;
        seed_rom[913] = 20'h43A67;
        seed_rom[914] = 20'h439D8;
        seed_rom[915] = 20'h43949;
        seed_rom[916] = 20'h438BA;
        seed_rom[917] = 20'h4382C;
        seed_rom[918] = 20'h4379D;
        seed_rom[919] = 20'h4370F;
        seed_rom[920] = 20'h43681;
        seed_rom[921] = 20'h435F3;
        seed_rom[922] = 20'h43565;
        seed_rom[923] = 20'h434D8;
        seed_rom[924] = 20'h4344A;
        seed_rom[925] = 20'h433BD;
        seed_rom[926] = 20'h43330;
        seed_rom[927] = 20'h432A3;
        seed_rom[928] = 20'h43216;
        seed_rom[929] = 20'h43189;
        seed_rom[930] = 20'h430FD;
        seed_rom[931] = 20'h43070;
        seed_rom[932] = 20'h42FE4;
        seed_rom[933] = 20'h42F58;
        seed_rom[934] = 20'h42ECC;
        seed_rom[935] = 20'h42E40;
        seed_rom[936] = 20'h42DB4;
        seed_rom[937] = 20'h42D28;
        seed_rom[938] = 20'h42C9D;
        seed_rom[939] = 20'h42C11;
        seed_rom[940] = 20'h42B86;
        seed_rom[941] = 20'h42AFB;
        seed_rom[942] = 20'h42A70;
        seed_rom[943] = 20'h429E6;
        seed_rom[944] = 20'h4295B;
        seed_rom[945] = 20'h428D0;
        seed_rom[946] = 20'h42846;
        seed_rom[947] = 20'h427BC;
        seed_rom[948] = 20'h42732;
        seed_rom[949] = 20'h426A8;
        seed_rom[950] = 20'h4261E;
        seed_rom[951] = 20'h42595;
        seed_rom[952] = 20'h4250B;
        seed_rom[953] = 20'h42482;
        seed_rom[954] = 20'h423F8;
        seed_rom[955] = 20'h4236F;
        seed_rom[956] = 20'h422E6;
        seed_rom[957] = 20'h4225E;
        seed_rom[958] = 20'h421D5;
        seed_rom[959] = 20'h4214C;
        seed_rom[960] = 20'h420C4;
        seed_rom[961] = 20'h4203C;
        seed_rom[962] = 20'h41FB4;
        seed_rom[963] = 20'h41F2C;
        seed_rom[964] = 20'h41EA4;
        seed_rom[965] = 20'h41E1C;
        seed_rom[966] = 20'h41D95;
        seed_rom[967] = 20'h41D0D;
        seed_rom[968] = 20'h41C86;
        seed_rom[969] = 20'h41BFF;
        seed_rom[970] = 20'h41B78;
        seed_rom[971] = 20'h41AF1;
        seed_rom[972] = 20'h41A6A;
        seed_rom[973] = 20'h419E3;
        seed_rom[974] = 20'h4195D;
        seed_rom[975] = 20'h418D7;
        seed_rom[976] = 20'h41850;
        seed_rom[977] = 20'h417CA;
        seed_rom[978] = 20'h41744;
        seed_rom[979] = 20'h416BF;
        seed_rom[980] = 20'h41639;
        seed_rom[981] = 20'h415B3;
        seed_rom[982] = 20'h4152E;
        seed_rom[983] = 20'h414A9;
        seed_rom[984] = 20'h41423;
        seed_rom[985] = 20'h4139E;
        seed_rom[986] = 20'h4131A;
        seed_rom[987] = 20'h41295;
        seed_rom[988] = 20'h41210;
        seed_rom[989] = 20'h4118C;
        seed_rom[990] = 20'h41107;
        seed_rom[991] = 20'h41083;
        seed_rom[992] = 20'h40FFF;
        seed_rom[993] = 20'h40F7B;
        seed_rom[994] = 20'h40EF7;
        seed_rom[995] = 20'h40E73;
        seed_rom[996] = 20'h40DF0;
        seed_rom[997] = 20'h40D6C;
        seed_rom[998] = 20'h40CE9;
        seed_rom[999] = 20'h40C66;
        seed_rom[1000] = 20'h40BE3;
        seed_rom[1001] = 20'h40B60;
        seed_rom[1002] = 20'h40ADD;
        seed_rom[1003] = 20'h40A5B;
        seed_rom[1004] = 20'h409D8;
        seed_rom[1005] = 20'h40956;
        seed_rom[1006] = 20'h408D3;
        seed_rom[1007] = 20'h40851;
        seed_rom[1008] = 20'h407CF;
        seed_rom[1009] = 20'h4074D;
        seed_rom[1010] = 20'h406CB;
        seed_rom[1011] = 20'h4064A;
        seed_rom[1012] = 20'h405C8;
        seed_rom[1013] = 20'h40547;
        seed_rom[1014] = 20'h404C6;
        seed_rom[1015] = 20'h40445;
        seed_rom[1016] = 20'h403C4;
        seed_rom[1017] = 20'h40343;
        seed_rom[1018] = 20'h402C2;
        seed_rom[1019] = 20'h40241;
        seed_rom[1020] = 20'h401C1;
        seed_rom[1021] = 20'h40140;
        seed_rom[1022] = 20'h400C0;
        seed_rom[1023] = 20'h40040;
    end

    // ------------------------------------------------------------------------------
    // Stage 0 (comb): unpack, classify, normalize, exponent plan, special results
    // ------------------------------------------------------------------------------
    logic         sgn_s0;      // Operand sign
    logic [10:0]  exp_s0;      // Raw biased exponent field
    logic [51:0]  frac_s0;     // Raw fraction field
    logic [5:0]   msb_s0;      // MSB position of a subnormal fraction
    logic [52:0]  m_s0;        // Normalized significand, UQ1.52
    logic signed [12:0] e_s0;      // Unbiased exponent of a (-1074..1023)
    logic signed [12:0] er_s0;     // Result exponent, general path: -e-1
    logic signed [12:0] er0_s0;    // Result exponent, power-of-two path: -e
    logic signed [12:0] biased_s0; // er_s0 + 1023
    logic         pow2_s0;     // Significand is exactly 1.0 (a = +-2^k)
    logic         spec_s0;     // Result comes from the bypass path
    logic [63:0]  sres_s0;     // Bypass result
    logic [3:0]   sflg_s0;     // Bypass flags
    logic [10:0]  expf_s0;     // Result exponent field (normal general path)
    logic [1:0]   shift_s0;    // Denormalization shift of the result (0/1/2)
    logic [9:0]   idx_s0;      // Seed ROM index (top 10 fraction bits of m)

    // Function: msb_pos
    // Purpose: index of the most significant set bit of a 52-bit fraction (priority encoder)
    function automatic logic [5:0] msb_pos(input logic [51:0] f);
        integer i;
        begin
            msb_pos = 6'd0;
            for (i = 0; i < 52; i = i + 1) begin
                if (f[i]) begin
                    msb_pos = i[5:0];
                end
            end
        end
    endfunction

    always_comb begin
        sgn_s0  = a[63];
        exp_s0  = a[62:52];
        frac_s0 = a[51:0];
        msb_s0  = msb_pos(frac_s0);

        // Normalize (subnormal input: shift the MSB of the fraction up to bit 52)
        if (exp_s0 == 11'd0) begin
            m_s0 = {1'b0, frac_s0} << (7'd52 - {1'b0, msb_s0});
            e_s0 = $signed({7'b0, msb_s0}) - 13'sd1074;
        end else begin
            m_s0 = {1'b1, frac_s0};
            e_s0 = $signed({2'b0, exp_s0}) - 13'sd1023;
        end

        pow2_s0   = ~(|m_s0[51:0]);
        er_s0     = -e_s0 - 13'sd1;
        er0_s0    = -e_s0;
        biased_s0 = er_s0 + 13'sd1023;
        idx_s0    = m_s0[51:42];

        // Denormalization shift (only meaningful on the general path; biased >= -1 there
        // because 1/|a| >= 2^-1024 whenever the result does not overflow)
        if (biased_s0 >= 13'sd1) begin
            shift_s0 = 2'd0;
        end else if (biased_s0 == 13'sd0) begin
            shift_s0 = 2'd1;
        end else begin
            shift_s0 = 2'd2;
        end
        expf_s0 = biased_s0[10:0];

        // Bypass path: NaN, inf, zero, exact powers of two, and general-path overflow
        spec_s0 = 1'b1;
        sres_s0 = QNAN;
        sflg_s0 = 4'b0000;
        if (exp_s0 == 11'h7FF) begin
            if (frac_s0 != 52'd0) begin
                sres_s0 = QNAN;                              // NaN in -> canonical qNaN
                sflg_s0 = {~frac_s0[51], 3'b000};            // invalid only for sNaN
            end else begin
                sres_s0 = {sgn_s0, 63'd0};                   // 1/inf = signed zero
            end
        end else if ((exp_s0 == 11'd0) && (frac_s0 == 52'd0)) begin
            sres_s0 = {sgn_s0, 11'h7FF, 52'd0};              // 1/0 = signed inf
            sflg_s0 = 4'b0100;                               // divzero
        end else if (pow2_s0) begin
            if (er0_s0 >= 13'sd1024) begin
                sres_s0 = {sgn_s0, 11'h7FF, 52'd0};          // 2^k overflows -> inf
                sflg_s0 = 4'b0010;                           // overflow
            end else if (er0_s0 >= -13'sd1022) begin
                sres_s0 = {sgn_s0, er0_s0[10:0] + 11'd1023, 52'd0}; // exact normal 2^-k
            end else begin
                sres_s0 = {sgn_s0, 11'd0, 1'b1, 51'd0};      // exact subnormal 2^-1023
            end
        end else if (er_s0 >= 13'sd1024) begin
            sres_s0 = {sgn_s0, 11'h7FF, 52'd0};              // general-path overflow
            sflg_s0 = 4'b0010;                               // overflow
        end else begin
            spec_s0 = 1'b0;
        end
    end

    // ------------------------------------------------------------------------------
    // Side pipes (stage 1..11): significand and packing metadata ride alongside
    // ------------------------------------------------------------------------------
    logic [52:0] m_pipe    [1:11];  // Normalized significand M, UQ1.52
    logic [11:1] sgn_pipe;          // Result sign
    logic [11:1] spec_pipe;         // Bypass-path marker
    logic [63:0] sres_pipe [1:11];  // Bypass result
    logic [3:0]  sflg_pipe [1:11];  // Bypass flags
    logic [10:0] expf_pipe [1:11];  // Result exponent field (normal path)
    logic [1:0]  shift_pipe [1:11]; // Result denormalization shift

    always_ff @(posedge clk) begin
        integer i;
        m_pipe[1]     <= m_s0;
        sgn_pipe[1]   <= sgn_s0;
        spec_pipe[1]  <= spec_s0;
        sres_pipe[1]  <= sres_s0;
        sflg_pipe[1]  <= sflg_s0;
        expf_pipe[1]  <= expf_s0;
        shift_pipe[1] <= shift_s0;
        for (i = 2; i <= 11; i = i + 1) begin
            m_pipe[i]     <= m_pipe[i-1];
            sgn_pipe[i]   <= sgn_pipe[i-1];
            spec_pipe[i]  <= spec_pipe[i-1];
            sres_pipe[i]  <= sres_pipe[i-1];
            sflg_pipe[i]  <= sflg_pipe[i-1];
            expf_pipe[i]  <= expf_pipe[i-1];
            shift_pipe[i] <= shift_pipe[i-1];
        end
    end

    // ------------------------------------------------------------------------------
    // Stage 1: ROM index register; Stage 2: synchronous seed ROM read
    // ------------------------------------------------------------------------------
    logic [9:0]  idx_q1;  // Registered ROM index
    logic [19:0] y0_q2;   // Seed y0, UQ1.19
    logic [19:0] y0_q3;   // Seed piped to the iteration-1 multiply

    always_ff @(posedge clk) begin
        idx_q1 <= idx_s0;
        y0_q2  <= seed_rom[idx_q1];
        y0_q3  <= y0_q2;
    end

    // ------------------------------------------------------------------------------
    // NR iteration 1 (stages 3-4): t1 = 2 - m*y0 (UQ2.30), y1 = y0*t1 (UQ1.28)
    // ------------------------------------------------------------------------------
    logic [72:0] p1_s3;    // m*y0, UQ2.71
    logic [31:0] t1_s3;    // 2 - m*y0, UQ2.30
    logic [31:0] t1_q3;    // Registered t1
    logic [51:0] py1_s4;   // y0*t1, UQ3.49
    logic [28:0] y1_s4;    // y1, UQ1.28 (value < 1)
    logic [28:0] y1_q4;    // Registered y1
    logic [28:0] y1_q5;    // y1 piped to the iteration-2 multiply

    always_comb begin
        p1_s3  = m_pipe[2] * y0_q2;
        t1_s3  = 32'h8000_0000 - p1_s3[72:41];
        py1_s4 = y0_q3 * t1_q3;
        y1_s4  = py1_s4[49:21];
    end

    always_ff @(posedge clk) begin
        t1_q3 <= t1_s3;
        y1_q4 <= y1_s4;
        y1_q5 <= y1_q4;
    end

    // ------------------------------------------------------------------------------
    // NR iteration 2 (stages 5-6): t2 = 2 - m*y1 (UQ2.58), y2 = y1*t2 (UQ1.57)
    // ------------------------------------------------------------------------------
    logic [81:0]  p2_s5;   // m*y1, UQ2.80
    logic [59:0]  t2_s5;   // 2 - m*y1, UQ2.58
    logic [59:0]  t2_q5;   // Registered t2
    logic [88:0]  py2_s6;  // y1*t2, UQ3.86
    logic [57:0]  y2_s6;   // y2, UQ1.57 (value < 1)
    logic [57:0]  y2_q6;   // Registered y2
    logic [57:0]  y2_q7;   // y2 piped to the iteration-3 multiply

    always_comb begin
        p2_s5  = m_pipe[4] * y1_q4;
        t2_s5  = 60'h800_0000_0000_0000 - p2_s5[81:22];
        py2_s6 = y1_q5 * t2_q5;
        y2_s6  = py2_s6[86:29];
    end

    always_ff @(posedge clk) begin
        t2_q5 <= t2_s5;
        y2_q6 <= y2_s6;
        y2_q7 <= y2_q6;
    end

    // ------------------------------------------------------------------------------
    // NR iteration 3 (stages 7-8): t3 = 2 - m*y2 (UQ2.57), y3 = y2*t3 (UQ1.57)
    // ------------------------------------------------------------------------------
    logic [110:0] p3_s7;   // m*y2, UQ2.109
    logic [58:0]  t3_s7;   // 2 - m*y2, UQ2.57
    logic [58:0]  t3_q7;   // Registered t3
    logic [116:0] py3_s8;  // y2*t3, UQ3.114
    logic [57:0]  y3_s8;   // y3, UQ1.57 (value < 1, |1 - m*y3| < 2^-54)
    logic [57:0]  y3_q8;   // Registered y3
    logic [57:0]  y3_q9;   // y3 piped to the compensation multiply

    always_comb begin
        p3_s7  = m_pipe[6] * y2_q6;
        t3_s7  = 59'h400_0000_0000_0000 - p3_s7[110:52];
        py3_s8 = y2_q7 * t3_q7;
        y3_s8  = py3_s8[114:57];
    end

    always_ff @(posedge clk) begin
        t3_q7 <= t3_s7;
        y3_q8 <= y3_s8;
        y3_q9 <= y3_q8;
    end

    // ------------------------------------------------------------------------------
    // Compensated step (stages 9-10): r = 1 - m*y3 EXACT (residual of the widened
    // multiply, weight 2^-109, sliced to weight 2^-64); y' = y3 + y3*r in UQ1.62
    // ------------------------------------------------------------------------------
    localparam logic [109:0] ONE_Q109 = {1'b1, 109'b0};  // 1.0 with weight 2^-109

    logic [110:0]        pf_s9;    // m*y3 exact, UQ2.109
    logic signed [111:0] rf_s9;    // r = 1 - m*y3, signed, weight 2^-109
    logic signed [15:0]  r64_s9;   // r sliced to weight 2^-64 (|r| < 2^-54 => fits)
    logic signed [15:0]  r64_q9;   // Registered r slice
    logic signed [74:0]  corr_s10; // y3*r, signed, weight 2^-121
    logic signed [15:0]  ch_s10;   // Correction truncated to weight 2^-62
    logic [62:0]         yp_s10;   // y' = y3 + y3*r, UQ1.62
    logic [62:0]         yp_q10;   // Registered y'

    always_comb begin
        pf_s9    = m_pipe[8] * y3_q8;
        rf_s9    = $signed({2'b00, ONE_Q109}) - $signed({1'b0, pf_s9});
        r64_s9   = rf_s9[60:45];
        corr_s10 = $signed({1'b0, y3_q9}) * r64_q9;
        ch_s10   = corr_s10[74:59];
        yp_s10   = {y3_q9, 5'b00000} + {{47{ch_s10[15]}}, ch_s10};
    end

    always_ff @(posedge clk) begin
        r64_q9 <= r64_s9;
        yp_q10 <= yp_s10;
    end

    // ------------------------------------------------------------------------------
    // Candidate (stage 11): C = round(y' * 2^(p+1)), p = 52 - shift
    // ------------------------------------------------------------------------------
    logic [3:0]  sh_s11;   // Truncation shift 61-p = 9 + denorm shift
    logic [63:0] cf_s11;   // y' + rounding half, then >> sh
    logic [53:0] c_s11;    // Candidate significand at p+1 bits
    logic [53:0] c_q11;    // Registered candidate

    always_comb begin
        sh_s11 = 4'd9 + {2'b00, shift_pipe[10]};
        cf_s11 = ({1'b0, yp_q10} + (64'd1 << (sh_s11 - 4'd1))) >> sh_s11;
        c_s11  = cf_s11[53:0];
    end

    always_ff @(posedge clk) begin
        c_q11 <= c_s11;
    end

    // ------------------------------------------------------------------------------
    // Residual-sign RNE + pack (stage 12): A1 = 2^(54+p) + M - 2CM, A2 = A1 - 2M
    // ------------------------------------------------------------------------------
    logic [106:0]        cm_s12;   // C*M exact
    logic [107:0]        w2_s12;   // 2*C*M
    logic [109:0]        pw_s12;   // 2^(54+p) (p = 52 - shift)
    logic signed [110:0] a1_s12;   // 2^(54+p) + M - 2CM : sign of X - (C - 1/2)
    logic signed [110:0] a2_s12;   // A1 - 2M           : sign of X - (C + 1/2)
    logic [53:0]         r_s12;    // RNE-correct significand at p+1 bits
    logic [63:0]         res_s12;  // Packed result
    logic [3:0]          flg_s12;  // Packed flags
    logic [63:0]         res_q12;  // Registered result
    logic [3:0]          flg_q12;  // Registered flags

    always_comb begin
        cm_s12 = c_q11 * m_pipe[11];
        w2_s12 = {cm_s12, 1'b0};
        case (shift_pipe[11])
            2'd1:    pw_s12 = {5'b00001, 105'b0};        // 2^105 (p = 51)
            2'd2:    pw_s12 = {6'b000001, 104'b0};       // 2^104 (p = 50)
            default: pw_s12 = {4'b0001, 106'b0};         // 2^106 (p = 52)
        endcase
        a1_s12 = $signed({1'b0, pw_s12}) + $signed({58'd0, m_pipe[11]})
                 - $signed({3'b000, w2_s12});
        a2_s12 = a1_s12 - $signed({57'd0, m_pipe[11], 1'b0});
        if (a1_s12 < 0) begin
            r_s12 = c_q11 - 54'd1;
        end else if (a2_s12 > 0) begin
            r_s12 = c_q11 + 54'd1;
        end else begin
            r_s12 = c_q11;
        end

        if (spec_pipe[11]) begin
            res_s12 = sres_pipe[11];
            flg_s12 = sflg_pipe[11];
        end else if (shift_pipe[11] == 2'd0) begin
            res_s12 = {sgn_pipe[11], expf_pipe[11], r_s12[51:0]};   // normal
            flg_s12 = 4'b0000;
        end else begin
            res_s12 = {sgn_pipe[11], 10'b0, r_s12[52:0]};           // subnormal
            flg_s12 = 4'b0001;                                      // underflow (inexact)
        end
    end

    always_ff @(posedge clk) begin
        res_q12 <= res_s12;
        flg_q12 <= flg_s12;
    end

    // ------------------------------------------------------------------------------
    // Result delay line (stages 13..22): pad every path to LATENCY = 22
    // ------------------------------------------------------------------------------
    logic [63:0] res_pipe [0:NDELAY-1];  // Result delay line
    logic [3:0]  flg_pipe [0:NDELAY-1];  // Flags delay line

    always_ff @(posedge clk) begin
        integer i;
        res_pipe[0] <= res_q12;
        flg_pipe[0] <= flg_q12;
        for (i = 1; i < NDELAY; i = i + 1) begin
            res_pipe[i] <= res_pipe[i-1];
            flg_pipe[i] <= flg_pipe[i-1];
        end
    end

    assign result = res_pipe[NDELAY-1];
    assign flags  = flg_pipe[NDELAY-1];

    // ------------------------------------------------------------------------------
    // Unused slice aggregation (truncated low product bits and constant-zero heads)
    // ------------------------------------------------------------------------------
    logic unused_slices;  // Reduction of intentionally dropped bits
    assign unused_slices = &{1'b0, p1_s3[40:0], py1_s4[51:50], py1_s4[20:0],
                             p2_s5[21:0], py2_s6[88:87], py2_s6[28:0],
                             p3_s7[51:0], py3_s8[116:115], py3_s8[56:0],
                             rf_s9[44:0], corr_s10[58:0], cf_s11[63:54], r_s12[53],
                             er0_s0[12:11], biased_s0[12:11]};

`ifdef VERILATOR
    // Synthesis guard, not lint silencing: Yosys `synth` cannot parse `assert property`
    // (probe: TOK_PROPERTY syntax error), and Verilator defines VERILATOR for both
    // lint and simulation, so the assertions are active everywhere they can run.

    // rtl_contracts.md: an SVA inside each II-limited unit asserts in_valid never
    // violates II = 2 (valid_q[0] is in_valid delayed one cycle).
    property p_ii2;
        @(posedge clk) disable iff (!rst_n) !(in_valid && valid_q[0]);
    endproperty
    assert property (p_ii2)
        else $error("fp64_rcp_nr: II = 2 violated (back-to-back in_valid)");

    // Convergence guard for the compensated step: |1 - m*y3| < 2^-54, i.e. the signed
    // residual slice r64 loses nothing (rf bits above 2^-49-weight are sign extension).
    always_ff @(posedge clk) begin
        if (rst_n && valid_q[7] && !spec_pipe[8]) begin
            assert (rf_s9[111:60] == {52{rf_s9[60]}})
                else $error("fp64_rcp_nr: NR residual out of bounds");
        end
        if (rst_n && valid_q[9] && !spec_pipe[10]) begin
            assert ((yp_q10 > {2'b01, 61'b0}) && (yp_q10[62] == 1'b0))
                else $error("fp64_rcp_nr: y' out of (0.5, 1.0)");
        end
    end
`endif

endmodule
`default_nettype wire
