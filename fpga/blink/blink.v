module blink (
    input clk,
    output led
);
    reg [23:0] counter;
    always @(posedge clk)
        counter <= counter + 1;
    assign led = counter[23];
endmodule
