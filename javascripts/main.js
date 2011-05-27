var sensorlist = ["AF3","F7","F3","FC5","T7","P7","O1","O2","P8","T8","FC6","F4","F8","AF4"];

var papers = {};
var buffer = {};
var baselines = {};
var first = true;
var data = null;
var measurements = 0;

var normalize = function(v, loc) {
  return papers[loc].height/2 + (baselines[loc]-v)*0.5;
};

var drawLine = function (paper, x1, y1, x2, y2) {
    c =paper.path("M"+x1 + " "+ y1 + "L" + x2 + " " + y2);
    c.attr({stroke:'#006400', 'stroke-width': 2 });
};

var update = function(sensor) {
    papers[sensor].clear();
    t = papers[sensor].text(30, papers[sensor].height/2, sensor);
    t.attr({
               'fill':'#FFFFFF',
               'font-size': 30,
               'font-family': 'Helvetica'
           });

    for (i=0; i < buffer[sensor].length; i++) {
        drawLine(papers[sensor], 70 + i*30, buffer[sensor][i], 70 + (i+1)*30, buffer[sensor][i+1]);
  }
};

var refresh = function() {
    _(sensorlist).map(function(sensor) {
                          update(sensor);
                      });
};

var get_json = function(data) {
    var split = data.split(' ');
    
    var values = [];
    for (i=0; i<split.length; i++){
        values[i] = parseInt(split[i]);
    }
    
    var result = {
        'counter': values[0],
        'gyroX': values[1],
        'gyroY': values[2]
    };
    
    for (i=3; i < values.length; i++) {
        result[sensorlist[i-3]] = values[i];
    }

    return result;
};


var main = function() {
    _(sensorlist).map(
        function(sensor) {
            papers[sensor] = Raphael($("#"+sensor)[0]);
            buffer[sensor] = [];
            for (i=0; i<100; i++) {
                buffer[sensor][i] = papers[sensor].height/2;
            }             
        });
    refresh();
    
    var sock = new WebSocket("ws://0.0.0.0:8080");
    
    sock.onmessage = function(evt) {
        data = get_json(evt.data);
        _(buffer).map(
            function(buf, sensor) {
                if (first) {
                    baselines[sensor] = data[sensor];
                }
                buf.pop();
                buf.unshift(normalize(data[sensor], sensor));
                update(sensor);    
            });
        if (first) {
            first = false;
        }
    };
};





