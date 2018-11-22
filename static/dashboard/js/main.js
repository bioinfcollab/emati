const chartColors = {
    red: 'rgb(255, 99, 132)',
    orange: 'rgb(255, 159, 64)',
    yellow: 'rgb(255, 205, 86)',
    green: 'rgb(75, 193, 102)',
    blue: 'rgb(54, 162, 235)',
    purple: 'rgb(153, 102, 255)',
    grey: 'rgb(201, 203, 207)'
}

/* The default line chart configuration */
const lineChartConfig = {
    scales: {
        yAxes: [{
            ticks: {
                beginAtZero:true
            }
        }],
        xAxes: [{
            type: 'time',
            ticks: {
                autoSkip: true,
                maxTicksLimit: 20
            }
        }]
    },
    legend: {
        position: 'bottom',
    },
    tooltips: {
        position: 'nearest',
        mode: 'index',
        intersect: false,
    },
}
const pieChartConfig = {
    responsive: true,
    legend: {
        display: false,
        position: 'bottom',
    }
}


$(document).ready(function() {
    $(".chart").hide();
    $.get({
        url: 'ajax/stats',
        success: function(response) {
            $(".chart").show();
            $(".loading-icon").hide();
            const stats = response.statistics;
            const current = response.current;

            new Chart(document.getElementById('usersChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: stats.labels,
                    datasets: [{
                        label: 'Registered users',
                        backgroundColor: chartColors.red,
                        borderColor: chartColors.red,
                        data: stats.data.num_registered_users,
                        fill: false,
                    }, {
                        label: 'Verified users',
                        backgroundColor: chartColors.blue,
                        borderColor: chartColors.blue,
                        data: stats.data.num_verified_users,
                        fill: false,
                    }]
                },
                options: lineChartConfig
            });

            new Chart(document.getElementById('activeUsersChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: stats.labels,
                    datasets: [{
                        label: 'Active users',
                        backgroundColor: chartColors.red,
                        borderColor: chartColors.red,
                        data: stats.data.num_active_users,
                        fill: false,
                    }, {
                        label: 'Returning users',
                        backgroundColor: chartColors.blue,
                        borderColor: chartColors.blue,
                        data: stats.data.num_returning_users,
                        fill: false,
                    }]
                },
                options: lineChartConfig
            });

            new Chart(document.getElementById('signupDistributionChart').getContext('2d'), {
                type: 'pie',
                data: {
                    labels: [
                        ' Google',
                        ' Facebook',
                        ' Other',
                    ],
                    datasets: [{
                        label: 'Signup methods',
                        backgroundColor: [
                            chartColors.red, 
                            chartColors.blue, 
                            chartColors.yellow
                        ],
                        data: [
                            current.signup_distribution.google,
                            current.signup_distribution.facebook,
                            current.signup_distribution.other,
                        ],
                    }]
                },
                options: pieChartConfig
            });
            $(".custom-label").append(
                "<div class='custom-label__label' style='color: " + chartColors.red + "'>Google: </div><div class='custom-label__value'>" + current.signup_distribution.google + "</div>" +
                "<div class='custom-label__label' style='color: " + chartColors.blue + "'>Facebook: </div><div class='custom-label__value'>" + current.signup_distribution.facebook + "</div>" +
                "<div class='custom-label__label' style='color: " + chartColors.yellow + "'>Other: </div><div class='custom-label__value'>" + current.signup_distribution.other + "</div>"
            );

            new Chart(document.getElementById('articlesChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: stats.labels,
                    datasets: [{
                        label: 'Articles',
                        backgroundColor: chartColors.red,
                        borderColor: chartColors.red,
                        data: stats.data.num_articles,
                        fill: false,
                    }, {
                        label: 'Recommendations',
                        backgroundColor: chartColors.blue,
                        borderColor: chartColors.blue,
                        data: stats.data.num_recommendations,
                        fill: false,
                    }]
                },
                options: lineChartConfig
            });

            new Chart(document.getElementById('interactionsChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: stats.labels,
                    datasets: [{
                        label: 'Clicks',
                        borderColor: chartColors.yellow,
                        backgroundColor: chartColors.yellow,
                        data: stats.data.num_clicks,
                        fill: false,
                    }, {
                        label: 'Likes',
                        borderColor: chartColors.green,
                        backgroundColor: chartColors.green,
                        data: stats.data.num_likes,
                        fill: false,
                    }, {
                        label: 'Dislikes',
                        borderColor: chartColors.red,
                        backgroundColor: chartColors.red,
                        data: stats.data.num_dislikes,
                        fill: false,
                    }]
                },
                options: lineChartConfig
            });

            new Chart(document.getElementById('clickedInteractionsChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: stats.labels,
                    datasets: [
                    {
                        label: 'Only clicked',
                        borderColor: chartColors.yellow,
                        backgroundColor: chartColors.yellow,
                        data: stats.data.num_articles_only_clicked,
                        fill: false,
                    },{
                        label: 'Clicked and Liked',
                        borderColor: chartColors.green,
                        backgroundColor: chartColors.green,
                        data: stats.data.num_articles_clicked_liked,
                        fill: false,
                    }, {
                        label: 'Clicked and Disliked',
                        borderColor: chartColors.red,
                        backgroundColor: chartColors.red,
                        data: stats.data.num_articles_clicked_disliked,
                        fill: false,
                    }]
                },
                options: lineChartConfig
            });

            new Chart(document.getElementById('searchRequestsChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: stats.labels,
                    datasets: [{
                        label: 'Search requests',
                        borderColor: chartColors.red,
                        backgroundColor: chartColors.red,
                        data: stats.data.num_search_requests,
                        fill: false,
                    }, {
                        label: 'Users utilizing the search',
                        borderColor: chartColors.blue,
                        backgroundColor: chartColors.blue,
                        data: stats.data.num_users_searched,
                        fill: false,
                    }]
                },
                options: lineChartConfig
            });

            setupMap(current.user_locations);
        }
    });
});


function setupMap(coordinates) {
    var southWest = L.latLng(-89.98155760646617, -180);
    var northEast = L.latLng(89.99346179538875, 180);
    var bounds = L.latLngBounds(southWest, northEast);

    var worldmap = L.map('worldmap', {
        maxBounds: bounds,
        maxBoundsViscosity: 1.0
    });
    var osmUrl = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    var osmAttrib = 'Map data © <a href="https://openstreetmap.org">OpenStreetMap</a> contributors';
    var osm = new L.TileLayer(osmUrl, {minZoom: 2, maxZoom: 16, attribution: osmAttrib});
    worldmap.addLayer(osm);
    
    var markers = L.markerClusterGroup({
        spiderfyOnMaxZoom: false,
        showCoverageOnHover: false,
    });
    
    for (var i = 0; i < coordinates.length; i++) {
        var c = coordinates[i];
        var lat = c[0];
        var lon = c[1];
        var title = lat + ', ' + lon;
        var marker = L.marker(new L.LatLng(lat, lon), { title: title });
        // marker.bindPopup(title);
        markers.addLayer(marker);
    }

    worldmap.addLayer(markers);
    worldmap.setView(new L.LatLng(51.050407, 13.737262), 2);

    // Only scroll when given focus
    worldmap.on('focus', function() { worldmap.scrollWheelZoom.enable(); });
    worldmap.on('blur', function() { worldmap.scrollWheelZoom.disable(); });
}

