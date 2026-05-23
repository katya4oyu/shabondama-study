use crate::detect::Detection;

const MAX_MISS: u32 = 5;
const MAX_DIST: f32 = 100.0;

#[derive(Debug, Clone)]
pub struct BubbleTrack {
    pub id: u32,
    pub x: f32,
    pub y: f32,
    pub r: f32,
    pub vx: f32,
    pub vy: f32,
    pub age: u32,
    pub miss_count: u32,
}

impl BubbleTrack {
    fn new(id: u32, det: &Detection) -> Self {
        Self { id, x: det.x, y: det.y, r: det.r, vx: 0.0, vy: 0.0, age: 1, miss_count: 0 }
    }

    fn update(&mut self, det: &Detection) {
        self.vx = det.x - self.x;
        self.vy = det.y - self.y;
        self.x = det.x;
        self.y = det.y;
        self.r = det.r;
        self.age += 1;
        self.miss_count = 0;
    }

    fn predict(&self) -> (f32, f32) {
        (self.x + self.vx, self.y + self.vy)
    }
}

pub struct Tracker {
    tracks: Vec<BubbleTrack>,
    next_id: u32,
}

impl Tracker {
    pub fn new() -> Self {
        Self { tracks: Vec::new(), next_id: 1 }
    }

    pub fn update(&mut self, detections: &[Detection]) -> Vec<BubbleTrack> {
        let mut matched_det = vec![false; detections.len()];
        let mut matched_track = vec![false; self.tracks.len()];

        // 各トラックに最近傍の検出を割り当て
        for (ti, track) in self.tracks.iter_mut().enumerate() {
            let (px, py) = track.predict();
            let best = detections.iter().enumerate()
                .filter(|(di, _)| !matched_det[*di])
                .min_by(|(_, a), (_, b)| {
                    let da = (a.x - px).hypot(a.y - py);
                    let db = (b.x - px).hypot(b.y - py);
                    da.partial_cmp(&db).unwrap()
                });

            if let Some((di, det)) = best {
                let dist = (det.x - px).hypot(det.y - py);
                if dist < MAX_DIST {
                    track.update(det);
                    matched_det[di] = true;
                    matched_track[ti] = true;
                }
            }
        }

        // マッチしなかったトラックのmiss_countをインクリメント
        for (ti, track) in self.tracks.iter_mut().enumerate() {
            if !matched_track[ti] {
                track.miss_count += 1;
            }
        }

        // miss_count > MAX_MISS のトラックを削除
        self.tracks.retain(|t| t.miss_count <= MAX_MISS);

        // 未マッチの検出を新規トラックとして追加
        for (di, det) in detections.iter().enumerate() {
            if !matched_det[di] {
                let id = self.next_id;
                self.next_id += 1;
                self.tracks.push(BubbleTrack::new(id, det));
            }
        }

        self.tracks.clone()
    }

    pub fn active_tracks(&self) -> &[BubbleTrack] {
        &self.tracks
    }
}

impl Default for Tracker {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn det(x: f32, y: f32, r: f32) -> Detection {
        Detection::new(x, y, r)
    }

    #[test]
    fn new_detection_creates_track_with_id_1() {
        let mut tracker = Tracker::new();
        let tracks = tracker.update(&[det(100.0, 100.0, 20.0)]);
        assert_eq!(tracks.len(), 1);
        assert_eq!(tracks[0].id, 1);
    }

    #[test]
    fn close_detection_continues_existing_track() {
        let mut tracker = Tracker::new();
        tracker.update(&[det(100.0, 100.0, 20.0)]);
        let tracks = tracker.update(&[det(105.0, 105.0, 20.0)]);
        assert_eq!(tracks.len(), 1);
        assert_eq!(tracks[0].id, 1);
        assert_eq!(tracks[0].age, 2);
    }

    #[test]
    fn far_detection_creates_new_track() {
        let mut tracker = Tracker::new();
        tracker.update(&[det(100.0, 100.0, 20.0)]);
        let tracks = tracker.update(&[det(500.0, 500.0, 20.0)]);
        assert_eq!(tracks.len(), 2);
    }

    #[test]
    fn track_removed_after_max_miss_frames() {
        let mut tracker = Tracker::new();
        tracker.update(&[det(100.0, 100.0, 20.0)]);
        for _ in 0..=MAX_MISS {
            tracker.update(&[]);
        }
        assert!(tracker.active_tracks().is_empty());
    }

    #[test]
    fn two_detections_get_different_ids() {
        let mut tracker = Tracker::new();
        let tracks = tracker.update(&[det(100.0, 100.0, 20.0), det(300.0, 300.0, 20.0)]);
        assert_eq!(tracks.len(), 2);
        assert_ne!(tracks[0].id, tracks[1].id);
    }
}
