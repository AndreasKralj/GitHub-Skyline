union() {
	difference() {
		polyhedron(faces = [[0, 1, 2, 3], [4, 5, 1, 0], [7, 6, 5, 4], [5, 6, 2, 1], [6, 7, 3, 2], [7, 4, 0, 3]], points = [[0, 0, 0], [150, 0, 0], [150, 30, 0], [0, 30, 0], [3.5, 3.5, 10], [146.5, 3.5, 10], [146.5, 26.5, 10], [3.5, 26.5, 10]]);
		rotate(a = [70.70995378081128, 0, 0]) {
			translate(v = [18.75, 1.75, -1]) {
				linear_extrude(height = 2) {
					scale(v = [0.04, 0.04, 0.04]) {
						import(file = "/Users/andrew.krall/Desktop/Workspace/pe-cope-github-skyline/github.svg", origin = [0, 0]);
					}
				}
			}
		}
	}
	rotate(a = [70.70995378081128, 0, 0]) {
		translate(v = [37.5, 3.25, -1.5]) {
			linear_extrude(height = 2) {
				text(size = 5, text = "@ak-vuhl");
			}
		}
	}
	rotate(a = [70.70995378081128, 0, 0]) {
		translate(v = [120.0, 2.25, -1.5]) {
			linear_extrude(height = 2) {
				text(size = 6, text = "2026");
			}
		}
	}
}
