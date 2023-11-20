import { TestBed } from '@angular/core/testing';

import { ScoutingDataService } from './scouting-data.service';

describe('ScoutingDataService', () => {
  let service: ScoutingDataService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ScoutingDataService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
